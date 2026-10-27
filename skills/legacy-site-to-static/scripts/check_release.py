#!/usr/bin/env python3
"""Check an explicit public directory, references, release metadata and basic static boundaries.

This is an offline consistency gate, not a complete security scanner or browser test.
Policy may be a project config containing a validation object, or that object alone.
"""
import argparse
from collections import Counter
import hashlib
from html.parser import HTMLParser
import json
import os
import posixpath
from pathlib import Path, PurePosixPath
import re
import stat
from urllib.parse import unquote, urljoin, urlsplit
from urllib.robotparser import RobotFileParser
from _common import check_output, emit, inside, output_args

EXTENSIONS = {'.html', '.htm', '.css', '.js', '.mjs', '.json', '.txt', '.xml', '.webmanifest',
              '.ico', '.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg', '.avif', '.woff', '.woff2',
              '.ttf', '.otf', '.pdf', '.mp4', '.webm', '.mp3'}
PRIVATE_PARTS = {'.git', '.svn', 'manager', 'local-state', 'backups', 'backup', 'node_modules'}
PRIVATE_FILES = {'.env', '.user.ini', 'content-backup.json', 'restore-info.json', 'project.private.json'}
SERVER_CODE = re.compile(r'\.(?:php\d*|phtml|phar|asp|aspx|jsp|cgi|py|cjs|ps1|cmd|bat|command|sql|sqlite\d*|pem|key)(?:\.|$)', re.I)
PRIVATE_ASSIGNMENT = re.compile(r'''["']?(DB_PWD|DB_PASSWORD|FTP_PASSWORD|CLIENT_SECRET|AWS_SECRET_ACCESS_KEY|TRANSLATOR_KEY)["']?\s*[:=]\s*["'][^"'\r\n]{7,}["']''', re.I)
PRIVATE_JSON = re.compile(r'"(?:editorAssets|enHistory|privateDrafts|ftpPassword|translationKey)"\s*:')
CSS_REFS = re.compile(r'url\(\s*([\'"]?)(.*?)\1\s*\)|@import\s+[\'"]([^\'"]+)[\'"]', re.I)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.refs, self.ids, self.problems, self.base = [], set(), [], None
        self.css, self.post_actions, self.in_style = [], set(), False
        self.noindex, self.has_title = False, False

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if attrs.get('id'):
            self.ids.add(attrs['id'])
        if tag == 'a' and attrs.get('name'):
            self.ids.add(attrs['name'])
        if tag == 'title':
            self.has_title = True
        if tag == 'base' and self.base is None:
            self.base = attrs.get('href')
        if tag == 'style':
            self.in_style = True
        if attrs.get('style'):
            self.css.append((attrs['style'], self.getpos()[0]))
        if tag == 'meta' and attrs.get('name', '').lower() in {'robots', 'googlebot'}:
            tokens = re.split(r'[\s,]+', attrs.get('content', '').lower())
            self.noindex |= 'noindex' in tokens or 'none' in tokens
        for key, value in attributes:
            if key.lower().startswith('on'):
                self.problems.append(('inline_event_handler', self.getpos()[0]))
            if key in {'href', 'src', 'poster', 'action'} and value and tag != 'base':
                self.refs.append((value, self.getpos()[0]))
            if value and re.match(r'\s*(?:javascript|vbscript)\s*:|\s*data:text/html', value, re.I):
                self.problems.append(('active_url', self.getpos()[0]))
        if attrs.get('srcset') and 'data:' not in attrs['srcset'].lower():
            self.refs.extend((part.strip().split()[0], self.getpos()[0]) for part in attrs['srcset'].split(',') if part.strip())
        if tag in {'iframe', 'object', 'embed'}:
            self.problems.append(('embed:' + (attrs.get('src') or attrs.get('data') or ''), self.getpos()[0]))
        if tag == 'form' and attrs.get('method', 'get').lower() != 'get':
            self.problems.append(('post_form:' + attrs.get('action', ''), self.getpos()[0]))
            self.post_actions.add(attrs.get('action', ''))

    def handle_endtag(self, tag):
        if tag == 'style':
            self.in_style = False

    def handle_data(self, data):
        if self.in_style:
            self.css.append((data, self.getpos()[0]))

    handle_startendtag = handle_starttag


def check(root, cfg, mode, base_url):
    issues, manifest, parsed, texts = [], [], {}, {}
    refs, external = 0, 0
    text_limit = int(cfg.get('max_text_bytes', 4 * 1024 * 1024))
    max_files = int(cfg.get('max_files', 20000))
    max_bytes = int(cfg.get('max_total_bytes', 128 * 1024 * 1024))
    if min(text_limit, max_files, max_bytes) < 1:
        raise ValueError('Release budgets must be positive.')
    extensions = EXTENSIONS | set(cfg.get('extra_extensions', []))
    extra = set(cfg.get('extra_public_files', []))
    reviewed_config = set(cfg.get('reviewed_static_config', []))
    downloads = set(cfg.get('public_download_archives', []))
    allowed_forms = set(cfg.get('allowed_post_form_actions', []))
    allowed_embeds = set(cfg.get('allowed_embed_urls', []))
    total = 0

    def issue(kind, path, line=None, severity='error', **detail):
        item = {'severity': severity, 'kind': kind, 'path': path}
        if line is not None:
            item['line'] = line
        item.update(detail)
        issues.append(item)

    if not root.is_dir():
        issue('public_directory_missing', '.')
        return {'ok': False, 'issues': issues, 'manifest': [], 'summary': {'errors': 1, 'warnings': 0}}
    exhausted = False
    def walk_error(error):
        bad = Path(error.filename) if error.filename else root
        issue('unreadable_directory', bad.relative_to(root).as_posix() if inside(bad, root) else '.', error=type(error).__name__)
    for folder, directories, files in os.walk(root, followlinks=False, onerror=walk_error):
        for name in list(directories):
            path = Path(folder) / name
            info = path.lstat()
            if path.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
                issue('link_not_allowed', path.relative_to(root).as_posix())
                directories.remove(name)
        for name in files:
            path = Path(folder) / name
            rel = path.relative_to(root).as_posix()
            if len(manifest) >= max_files:
                issue('file_budget_exceeded', '.', limit=max_files)
                exhausted = True
                break
            try:
                info = path.lstat()
                if not stat.S_ISREG(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                    issue('link_or_special_file_not_allowed', rel)
                    continue
                total += info.st_size
                if total > max_bytes:
                    issue('byte_budget_exceeded', '.', limit=max_bytes)
                    exhausted = True
                    break
                digest = hashlib.sha256()
                with path.open('rb') as stream:
                    for chunk in iter(lambda: stream.read(512 * 1024), b''):
                        digest.update(chunk)
                manifest.append({'path': rel, 'bytes': info.st_size, 'sha256': digest.hexdigest()})
                lower = rel.lower()
                if set(lower.split('/')) & PRIVATE_PARTS or path.name.lower() in PRIVATE_FILES or path.name.lower().startswith('.env.'):
                    issue('private_file_in_public_release', rel)
                if SERVER_CODE.search(path.name):
                    issue('server_code_or_sensitive_file', rel)
                if path.name.lower() in {'.htaccess', 'web.config'} and rel not in reviewed_config:
                    issue('runtime_config_requires_review', rel)
                if path.suffix.lower() == '.zip' and rel not in downloads:
                    issue('download_archive_requires_review', rel)
                elif path.suffix.lower() not in extensions and rel not in extra and rel not in reviewed_config and rel not in downloads:
                    issue('extension_requires_review', rel)
                if path.suffix.lower() in {'.html', '.htm', '.css', '.js', '.mjs', '.json', '.txt', '.xml', '.svg'}:
                    if info.st_size > text_limit:
                        issue('text_scan_limit', rel, severity='warning', limit=text_limit)
                        continue
                    text = path.read_text(encoding='utf-8-sig')
                    texts[rel] = text
                    if '<?php' in text.lower() or re.search(r'-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----', text):
                        issue('server_payload_or_private_key', rel)
                    for match in PRIVATE_ASSIGNMENT.finditer(text):
                        issue('credential_assignment_candidate', rel, text.count('\n', 0, match.start()) + 1, key=match.group(1).upper())
                    if PRIVATE_JSON.search(text):
                        issue('private_editing_metadata', rel)
                    if path.suffix.lower() in {'.html', '.htm'}:
                        page = Page();page.feed(text);page.close();parsed[rel] = page
                        if not page.has_title:
                            issue('missing_title', rel, severity='warning')
                        for kind, line in page.problems:
                            if kind.startswith('post_form:'):
                                if kind[len('post_form:'):] not in allowed_forms:
                                    issue('post_form_backend_not_declared', rel, line)
                            elif kind.startswith('embed:'):
                                if kind[len('embed:'):] not in allowed_embeds:
                                    issue('embedded_content_requires_review', rel, line)
                            else:
                                issue(kind, rel, line)
                    if path.suffix.lower() == '.svg' and re.search(r'<(?:script|foreignObject)\b|\bon\w+\s*=|(?:javascript|vbscript)\s*:', text, re.I):
                        issue('active_svg', rel)
            except (OSError, UnicodeError, ValueError) as error:
                issue('unreadable_or_invalid_text', rel, error=type(error).__name__)
        if exhausted:
            break

    base_url = base_url or 'https://release.invalid/'
    base = urlsplit(base_url)
    prefix = base.path if base.path.endswith('/') else base.path + '/'
    directory_index = cfg.get('directory_index', 'index.html')
    known_paths = {item['path'] for item in manifest}
    folded_paths = {name.casefold() for name in known_paths}

    def reference(owner, value, line=None, override=None):
        nonlocal refs, external
        if not value or value.startswith('#') and len(value) == 1:
            return
        try:
            document = urljoin(base_url, owner)
            target = urlsplit(urljoin(urljoin(document, override) if override else document, value))
        except ValueError:
            issue('invalid_reference_url', owner, line)
            return
        if target.scheme in {'mailto', 'tel', 'sms', 'data'}:
            return
        if target.scheme not in {'http', 'https'}:
            issue('unsupported_or_local_machine_url', owner, line)
            return
        if (target.scheme, target.netloc) != (base.scheme, base.netloc):
            external += 1
            return
        refs += 1
        normalized = unquote(target.path)
        if not normalized.startswith(prefix):
            issue('reference_outside_public_base', owner, line)
            return
        path = root / normalized[len(prefix):]
        if not inside(path, root):
            issue('reference_escapes_public_directory', owner, line)
            return
        if path.is_dir() or target.path.endswith('/'):
            path = path / directory_index
        key = posixpath.normpath(path.relative_to(root).as_posix())
        if key not in known_paths:
            issue('local_reference_case_mismatch' if key.casefold() in folded_paths else 'missing_local_reference', owner, line, target=key)
            return
        if target.fragment and key in parsed and unquote(target.fragment) not in parsed[key].ids:
            issue('missing_html_anchor', owner, line, target=key)

    for rel, page in parsed.items():
        for value, line in page.refs:
            if value in page.post_actions and value in allowed_forms:
                external += 1
                continue
            reference(rel, value, line, page.base)
        for css, line in page.css:
            for match in CSS_REFS.finditer(css):
                reference(rel, match.group(2) if match.group(2) is not None else match.group(3), line, page.base)
    for rel, text in texts.items():
        if rel.endswith('.css'):
            for match in CSS_REFS.finditer(text):
                reference(rel, match.group(2) if match.group(2) is not None else match.group(3), text.count('\n', 0, match.start()) + 1)

    required = cfg.get('required_pages', ['index.html'])
    for rel in required:
        if rel not in parsed:
            issue('required_page_missing_or_unchecked', rel)
    entries = cfg.get('indexable_pages', required[:1])
    if mode == 'formal' and cfg.get('require_indexing', True):
        for rel in entries:
            if rel not in parsed or parsed[rel].noindex:
                issue('formal_entry_not_indexable', rel)
        if 'robots.txt' in texts:
            robot = RobotFileParser();robot.parse(texts['robots.txt'].splitlines())
            if not robot.can_fetch('*', base_url):
                issue('robots_blocks_formal_homepage', 'robots.txt')
    elif mode == 'preview' and any(rel in parsed and not parsed[rel].noindex for rel in entries):
        issue('preview_entry_has_no_html_noindex_verify_headers', entries[0] if entries else '.', severity='warning')

    def read_json(rel):
        if not rel:
            return {}
        if rel not in texts:
            issue('metadata_file_missing_or_unchecked', rel)
            return {}
        try:
            data = json.loads(texts[rel])
            if not isinstance(data, dict):
                raise ValueError()
            return data
        except ValueError:
            issue('invalid_metadata_json', rel)
            return {}

    data = read_json(cfg.get('data_file'))
    version = read_json(cfg.get('version_file'))
    observed = {}
    for key, expected in cfg.get('expected_counts', {}).items():
        actual = len(data[key]) if isinstance(data.get(key), list) else version.get(key)
        observed[key] = actual
        if actual != expected:
            issue('content_count_mismatch', cfg.get('data_file') or '.', key=key, expected=expected, actual=actual)
        if isinstance(data.get(key), list) and key in version and version[key] != actual:
            issue('version_count_disagrees_with_content', cfg.get('version_file') or '.', key=key)
    for rule in cfg.get('record_pages', []):
        if not isinstance(rule, dict):
            issue('record_page_mapping_invalid', cfg.get('data_file') or '.')
            continue
        collection = rule.get('collection')
        records = data.get(collection) if isinstance(collection, str) else None
        pattern = rule.get('pattern', '')
        if not isinstance(records, list) or not isinstance(pattern, str) or '{id}' not in pattern:
            issue('record_page_mapping_invalid', cfg.get('data_file') or '.', collection=collection)
            continue
        for record in records:
            identifier = record.get(rule.get('id_field', 'id')) if isinstance(record, dict) else None
            if identifier is None or any(c in '/\\' or ord(c) < 32 or ord(c) == 127 for c in str(identifier)):
                issue('record_page_id_invalid', cfg.get('data_file') or '.', collection=collection)
                continue
            target = pattern.replace('{id}', str(identifier))
            if PurePosixPath(target).is_absolute() or '..' in PurePosixPath(target).parts or '\\' in target:
                issue('record_page_mapping_escapes_public', cfg.get('data_file') or '.', collection=collection)
            elif target not in known_paths:
                issue('record_page_missing', cfg.get('data_file') or '.', collection=collection, target=target)
    if cfg.get('expected_version') is not None and version.get('version') != cfg['expected_version']:
        issue('content_version_mismatch', cfg.get('version_file') or '.')
    previous = cfg.get('previous_confirmed_translations')
    metric = cfg.get('translation_count_field', 'confirmedTranslations')
    if previous is not None:
        actual = version.get(metric)
        observed['confirmed_translations'] = actual
        if not isinstance(actual, int):
            issue('translation_count_not_available', cfg.get('version_file') or '.', key=metric)
        elif actual < previous:
            issue('confirmed_translation_count_decreased', cfg.get('version_file') or '.',
                  severity='warning' if cfg.get('translation_decrease_accepted') else 'error', previous=previous, actual=actual)
    levels = Counter(item['severity'] for item in issues)
    return {'ok': levels['error'] == 0, 'summary': {'files': len(manifest), 'bytes': total, 'html_pages': len(parsed),
            'local_references': refs, 'external_references_not_fetched': external, 'errors': levels['error'], 'warnings': levels['warning']},
            'observed_counts': observed, 'issues': issues, 'manifest': sorted(manifest, key=lambda item: item['path'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('public_directory', type=Path)
    parser.add_argument('--mode', choices=['preview', 'formal'], default='preview')
    parser.add_argument('--policy', type=Path, help='Project JSON (validation object) or a validation object.')
    parser.add_argument('--base-url', help='Public base URL including a trailing slash; defaults to project deployment.public_base_url.')
    output_args(parser)
    args = parser.parse_args()
    try:
        check_output(args, [args.public_directory])
        project = json.loads(args.policy.read_text(encoding='utf-8')) if args.policy else {}
        if not isinstance(project, dict):
            raise ValueError('Project policy must be an object.')
        cfg = project.get('validation', project)
        if not isinstance(cfg, dict):
            raise ValueError('Validation policy must be an object.')
        base_url = args.base_url or project.get('deployment', {}).get('public_base_url')
        if base_url:
            url = urlsplit(base_url)
            if url.scheme not in {'https', 'http'} or not url.hostname or url.username or url.password or url.query or url.fragment or not url.path.endswith('/'):
                raise ValueError('Use an HTTP(S) base URL ending in /, without credentials or query.')
        report = check(args.public_directory.resolve(), cfg, args.mode, base_url)
        report.update({'tool': 'check_release', 'public_root': str(args.public_directory.resolve()), 'mode': args.mode})
        emit(report, args)
        return 0 if report['ok'] else 1
    except (ValueError, TypeError, OSError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    raise SystemExit(main())

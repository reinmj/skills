#!/usr/bin/env python3
"""Inventory directories and ZIP metadata without extracting or reading file bodies."""
import argparse
from collections import Counter, defaultdict
import datetime
import os
from pathlib import Path
import re
import stat
import zipfile
from _common import check_output, emit, output_args

SERVER = re.compile(r'\.(?:php\d*|phtml|phar|asp|aspx|jsp|cgi|pl|py|rb|cjs)$', re.I)
MEDIA = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg', '.ico', '.avif', '.mp4', '.webm', '.mp3'}
HINTS = {'thinkphp': 'ThinkPHP paths', 'wp-content': 'WordPress paths', 'wp-includes': 'WordPress paths',
         'ueditor': 'UEditor paths', 'kindeditor': 'KindEditor paths', 'composer.json': 'PHP dependency manifest',
         'package.json': 'JavaScript dependency manifest', 'web.config': 'IIS configuration'}


def classify(name):
    path = name.replace('\\', '/').lower()
    leaf = path.rsplit('/', 1)[-1]
    parts = set(path.split('/'))
    if re.search(r'\.(?:sql(?:\.gz)?|sqlite\d*|db)$', leaf):
        return 'database'
    if leaf == 'core' or re.fullmatch(r'core\.\d+', leaf) or leaf.endswith('.log') or parts.intersection({'logs', 'cache', 'tmp', 'temp'}):
        return 'possible_runtime_noise'
    if leaf in {'.env', '.htaccess', '.user.ini', 'web.config', 'config.php', 'settings.php'} or leaf.endswith(('.pem', '.key')):
        return 'configuration_or_private_candidate'
    if SERVER.search(leaf):
        return 'server_code'
    if Path(leaf).suffix in MEDIA:
        return 'media'
    if leaf.endswith(('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx')):
        return 'document'
    if leaf.endswith(('.html', '.htm', '.css', '.js', '.json', '.xml', '.txt', '.woff', '.woff2', '.ttf')):
        return 'static_or_data'
    if leaf.endswith(('.zip', '.gz', '.tar', '.7z', '.rar')):
        return 'archive'
    return 'other'


def inventory(source, limit, details):
    result = {'source': str(source.absolute()), 'format': 'filesystem', 'metadata_only': True,
              'truncated': False, 'counts': {}, 'bytes_by_category': {}, 'samples': {},
              'framework_path_hints': [], 'path_flags': [], 'errors': []}
    counts, sizes, samples, hints = Counter(), Counter(), defaultdict(list), set()
    rows, seen, folded = [], set(), {}
    examined = 0

    def add(name, kind, size=0, compressed=None):
        nonlocal examined
        if examined >= limit:
            result['truncated'] = True
            return False
        examined += 1
        normalized = name.replace('\\', '/')
        category = 'directory' if kind == 'directory' else 'link' if kind == 'link' else classify(name)
        counts[category] += 1
        sizes[category] += size if kind == 'file' else 0
        if len(samples[category]) < 12:
            samples[category].append({'path': name, 'bytes': size, 'compressed_bytes': compressed})
        flags = []
        if normalized.startswith('/') or re.match(r'^[A-Za-z]:', normalized) or '..' in normalized.split('/'):
            flags.append('unsafe_archive_path')
        if normalized in seen:
            flags.append('duplicate_normalized_path')
        if normalized.casefold() in folded and folded[normalized.casefold()] != normalized:
            flags.append('case_collision_for_case_insensitive_filesystem')
        seen.add(normalized)
        folded[normalized.casefold()] = normalized
        if kind == 'link':
            flags.append('link_not_traversed')
        if flags and len(result['path_flags']) < 100:
            result['path_flags'].append({'path': name, 'flags': flags})
        for component in normalized.lower().split('/'):
            if component in HINTS:
                hints.add(HINTS[component])
        if details:
            rows.append({'path': name, 'type': kind, 'bytes': size, 'compressed_bytes': compressed})
        return True

    def is_link(info):
        return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)

    try:
        root_info = source.lstat()
        if is_link(root_info):
            add(source.name, 'link')
        elif source.is_file() and source.suffix.lower() == '.zip':
            result['format'] = 'zip'
            with zipfile.ZipFile(source) as archive:
                info = archive.infolist()
                result['declared_archive_entries'] = len(info)
                for entry in info:
                    kind = 'link' if stat.S_ISLNK(entry.external_attr >> 16) else 'directory' if entry.is_dir() else 'file'
                    if not add(entry.filename, kind, entry.file_size, entry.compress_size):
                        break
        elif source.is_dir():
            def walk(folder):
                try:
                    with os.scandir(folder) as entries:
                        for entry in entries:
                            if result['truncated']:
                                return
                            relative = Path(entry.path).relative_to(source).as_posix()
                            try:
                                info = entry.stat(follow_symlinks=False)
                                kind = 'link' if is_link(info) else 'directory' if stat.S_ISDIR(info.st_mode) else 'file'
                                if add(relative, kind, info.st_size) and kind == 'directory':
                                    walk(Path(entry.path))
                            except OSError as error:
                                result['errors'].append({'path': relative, 'error': type(error).__name__})
                except OSError as error:
                    result['errors'].append({'path': str(folder), 'error': type(error).__name__})
            walk(source)
        else:
            add(source.name, 'file', root_info.st_size)
    except (OSError, zipfile.BadZipFile, RuntimeError) as error:
        result['errors'].append({'error': type(error).__name__})
    result.update({'entries_examined': examined, 'counts': dict(counts), 'bytes_by_category': dict(sizes),
                   'samples': dict(samples), 'framework_path_hints': sorted(hints)})
    if details:
        result['entries'] = rows
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sources', nargs='+', type=Path)
    parser.add_argument('--max-entries', type=int, default=50000, help='Maximum reported entries per input; ZIP central-directory loading is not memory-isolated.')
    parser.add_argument('--details', action='store_true', help='Include a full per-entry metadata list, up to the limit.')
    parser.add_argument('--strict', action='store_true', help='Return failure if an inventory is incomplete or has errors.')
    output_args(parser)
    args = parser.parse_args()
    if args.max_entries < 1:
        parser.error('--max-entries must be positive')
    try:
        check_output(args, args.sources)
    except ValueError as error:
        parser.error(str(error))
    items = [inventory(source, args.max_entries, args.details) for source in args.sources]
    incomplete = sum(bool(item['errors'] or item['truncated']) for item in items)
    report = {'tool': 'inventory_sources', 'ok': incomplete == 0,
              'summary': {'inputs': len(items), 'incomplete_inputs': incomplete}, 'sources': items}
    emit(report, args)
    return 1 if args.strict and incomplete else 0


if __name__ == '__main__':
    raise SystemExit(main())

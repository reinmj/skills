#!/usr/bin/env python3
"""Bounded GET checks for specified public URLs; no automatic redirects or body logging."""
import argparse
import hashlib
import json
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, HTTPSHandler
from _common import check_output, emit, output_args


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def safe_url(value):
    parsed = urlsplit(value)
    host = parsed.netloc.rsplit('@', 1)[-1]
    return urlunsplit((parsed.scheme, host, parsed.path, '[redacted]' if parsed.query else '', ''))


def probe(opener, url, expected, timeout, limit, host_header=None):
    result = {'url': safe_url(url), 'method': 'GET', 'expected_status': expected, 'status': None,
              'ok': False, 'tls_verification_enabled': urlsplit(url).scheme == 'https'}
    headers = {'User-Agent': 'LegacyStaticMigration-ReadOnlyCheck/1.0'}
    if host_header:
        headers['Host'] = host_header
    try:
        try:
            response = opener.open(Request(url, headers=headers, method='GET'), timeout=timeout)
        except HTTPError as error:
            response = error
        with response:
            body = response.read(limit + 1)
            truncated = len(body) > limit
            result.update({'status': response.code, 'server': response.headers.get('Server'),
                           'content_type': response.headers.get('Content-Type'),
                           'bytes_read': min(len(body), limit), 'body_truncated': truncated,
                           'body_sha256': None if truncated else hashlib.sha256(body).hexdigest(),
                           'location': safe_url(response.headers['Location']) if response.headers.get('Location') else None,
                           'ok': response.code == expected and not truncated})
    except Exception as error:
        result['error'] = type(error).__name__
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('urls', nargs='+')
    parser.add_argument('--expect-status', type=int, default=200)
    parser.add_argument('--timeout', type=float, default=10)
    parser.add_argument('--max-bytes', type=int, default=2 * 1024 * 1024)
    parser.add_argument('--host-header', help='Plain HTTP origin testing only; use curl --resolve for HTTPS Host/SNI.')
    output_args(parser)
    args = parser.parse_args()
    if len(args.urls) > 20 or args.timeout <= 0 or args.max_bytes < 1 or not 100 <= args.expect_status <= 599:
        parser.error('Use at most 20 URLs, positive limits, and a valid HTTP status.')
    for url in args.urls:
        try:
            parsed = urlsplit(url)
            if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username is not None or parsed.password is not None or any(ord(c) < 32 for c in url):
                raise ValueError()
            if args.host_header and parsed.scheme != 'http':
                parser.error('--host-header is for HTTP only; HTTPS requires correct SNI.')
        except ValueError:
            parser.error('URLs must be HTTP(S), without credentials or control characters.')
    if args.host_header and (any(c.isspace() or c in '/\\@' for c in args.host_header) or not args.host_header):
        parser.error('Invalid Host header.')
    try:
        check_output(args)
    except ValueError as error:
        parser.error(str(error))
    context = ssl.create_default_context()
    opener = build_opener(NoRedirect(), HTTPSHandler(context=context))
    checks = [probe(opener, url, args.expect_status, args.timeout, args.max_bytes, args.host_header) for url in args.urls]
    failed = sum(not item['ok'] for item in checks)
    emit({'tool': 'probe_routes', 'ok': failed == 0, 'summary': {'checked': len(checks), 'failed': failed}, 'checks': checks}, args)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())

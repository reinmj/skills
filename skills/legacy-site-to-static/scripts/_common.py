"""Private report output and path checks shared by the read-only helpers."""
import json
import os
from pathlib import Path


def inside(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except (ValueError, OSError):
        return False


def output_args(parser):
    parser.add_argument('--out', type=Path, help='Private JSON report outside the input/public directory.')
    parser.add_argument('--overwrite', action='store_true', help='Replace an existing report at --out.')


def check_output(args, forbidden=()):
    if args.out is None:
        return
    target = args.out.resolve()
    for source in forbidden:
        source = Path(source)
        if target == source.resolve() or inside(target, source):
            raise ValueError('Report output must be outside the input/public path.')
    if target.exists() and not args.overwrite:
        raise ValueError('Report already exists; choose another path or pass --overwrite.')


def emit(report, args):
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC if args.overwrite else os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(str(args.out), flags, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            if hasattr(os, 'fchmod'):
                os.fchmod(stream.fileno(), 0o600)
            stream.write(text + '\n')
        summary = {key: report[key] for key in ('tool', 'ok', 'summary') if key in report}
        summary['report'] = str(args.out.resolve())
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(text)

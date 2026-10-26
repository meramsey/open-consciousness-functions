"""Build relative-path indexes for a verified private listener package."""

import argparse
from pathlib import Path

from ocf_tools.private_collection_index import build_private_collection_index


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--progress", type=Path)
    args = parser.parse_args(argv)
    result = build_private_collection_index(args.package, args.output, progress=args.progress)
    print(f"Verified tracks: {result['verified_count']}; statuses: {result['status_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

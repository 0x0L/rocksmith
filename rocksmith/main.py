"""
Rocksmith 2014 CLI tools
"""

import json
import os
import sys

from .psarc import (
    PLATFORMS,
    PSARC,
    convert as psarc_convert,
    detect_platform,
    read_source,
)
from .sng import Song


def path2dict(path):
    n = len(path) + 1
    d = {}
    for dirpath, _, filenames in os.walk(path):
        for filename in filenames:
            fullpath = os.path.join(dirpath, filename)
            with open(fullpath, "rb") as fh:
                d[fullpath[n:]] = fh.read()
    return d


def dict2path(d, dest="."):
    for filepath, data in d.items():
        filename = os.path.join(dest, filepath)
        path = os.path.dirname(filename)
        if not os.path.exists(path):
            os.makedirs(path)
        with open(filename, "wb") as fh:
            fh.write(data)


def unpack(filename, crypto):
    with open(filename, "rb") as fh:
        content = PSARC(crypto).parse_stream(fh)
    destdir = os.path.splitext(os.path.basename(filename))[0]
    dict2path(content, destdir)


def pack(directory, crypto):
    content = path2dict(directory)
    dest = os.path.basename(directory) + ".psarc"
    # X360/PS3 store the plaintext container header big-endian
    source = detect_platform(content, flags=0)
    endian = "<" if crypto else PLATFORMS[source]["endian"]
    with open(dest, "wb") as fh:
        PSARC(crypto, endian=endian).build_stream(content, fh)


def print_sng(filename):
    with open(filename, "rb") as fh:
        sng = Song.parse_stream(fh)
        s = json.dumps(sng, indent=4, default=lambda _: None)
        g = "\n".join(l for l in s.splitlines() if '"_io"' not in l)
        print(g)


def convert(filename, platform):
    _, src = read_source(filename)
    if src == platform:
        # not an error: rebuilding an archive on its own platform is a
        # legitimate renormalization, but rarely what was meant
        print(
            "warning: %s already contains %s data" % (filename, platform),
            file=sys.stderr,
        )
    outname = psarc_convert(filename, platform)
    print(outname)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--no-crypto",
        help="do not perform cryptographic operations on sng files: pack "
        "writes a console-style plaintext archive",
        action="store_true",
    )

    parser.add_argument("--unpack", help="unpack a PSARC archive", metavar=("FILE",))

    parser.add_argument(
        "--pack", help="pack a DIRECTORY into a PSARC archive", metavar=("DIRECTORY",)
    )

    parser.add_argument(
        "--convert",
        help="convert a PSARC archive to --platform",
        metavar=("FILE",),
    )

    parser.add_argument(
        "--platform",
        help="target platform for --convert",
        choices=sorted(PLATFORMS),
    )

    parser.add_argument(
        "--print-sng",
        help="print a Rocksmith sng file as a JSON string",
        metavar=("FILE",),
    )

    args = parser.parse_args()
    if args.unpack:
        unpack(args.unpack, not args.no_crypto)
    elif args.pack:
        pack(args.pack, not args.no_crypto)
    elif args.convert:
        if not args.platform:
            parser.error("--convert requires --platform")
        convert(args.convert, args.platform)
    elif args.print_sng:
        print_sng(args.print_sng)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

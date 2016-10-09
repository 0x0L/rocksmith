"""
Command line interface to the rocksmith python package.
"""

import argparse
import os

from rocksmith import PSARC
from rocksmith.utils import path2dict, dict2path, encrypt_psarc, decrypt_psarc

def extract(filename, no_crypto):
    with open(filename, 'rb') as fh:
        psarc = PSARC.parse_stream(fh)
    if not no_crypto:
        decrypt_psarc(psarc)
    dest = os.path.splitext(os.path.basename(filename))[0]
    dict2path(psarc, dest)

def create(filepath, no_crypto):
    psarc = path2dict(filepath)
    if not no_crypto:
        encrypt_psarc(psarc)
    dest = os.path.splitext(os.path.basename(filepath))[0]
    with open(dest + '.psarc', 'wb') as fh:
        PSARC.build_stream(psarc, fh)

def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--no-crypto',
                        help='do NOT perform encryption/decryption operations',
                        action='store_true')

    parser.add_argument('--extract',
                        help='unpack a PSARC archive',
                        metavar=('PSARC',))

    parser.add_argument('--create',
                        help='create a PSARC archive',
                        metavar=('DIRECTORY',))

    args = parser.parse_args()

    if args.extract:
        extract(args.extract, args.no_crypto)
    elif args.create:
        create(args.create, args.no_crypto)

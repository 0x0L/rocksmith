"""
Command line interface to the rocksmith python package.
"""

def main():
    import argparse
    from rocksmith.utils import pack, unpack, print_sng

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--no-crypto',
                        help='do not perform encryption/decryption operations',
                        action='store_true')

    parser.add_argument('--unpack',
                        help='unpack a PSARC archive',
                        metavar=('FILE',))

    parser.add_argument('--pack',
                        help='pack a DIRECTORY into a PSARC archive',
                        metavar=('DIRECTORY',))

    parser.add_argument('--print-sng',
                        help='print a Rocksmith sng file as a JSON string',
                        metavar=('FILE',))

    args = parser.parse_args()
    if args.unpack:
        unpack(args.unpack, not args.no_crypto)
    if args.pack:
        pack(args.pack, not args.no_crypto)
    if args.print_sng:
        print_sng(args.print_sng)

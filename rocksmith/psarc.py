"""
Parser/builder for Rocksmith 2014 PSARC archives.

An archive is a table of contents (the "BOM") plus zlib-deflated entry
data. PC and Mac archives encrypt the BOM (AES-CFB) and wrap song data
in AES-CTR; console archives (Xbox 360, PS3, PS4) store both in the
clear, song data inside the plaintext "4a" container.

    >>> from rocksmith.psarc import PSARC
    >>> content = PSARC().parse_stream(open('song_p.psarc', 'rb'))
    >>> content.keys()
    dict_keys(['audio/windows/song.wem', ...])

The returned dict is enough to rebuild an equivalent file:

    >>> PSARC().build_stream(content, open('rebuilt.psarc', 'wb'))

Pass ``PSARC(crypto=False)`` to build console-layout (unencrypted)
archives; parsing always follows the archive's own header flags.
"""

import os
import re
import zlib
from hashlib import md5
from io import BytesIO

from construct import (
    Adapter,
    Bytes,
    BytesInteger,
    Const,
    Construct,
    GreedyRange,
    Int16ub,
    Int32ub,
    Struct,
    this,
)

from .crypto import (
    decrypt_bom,
    decrypt_psarc,
    encrypt_bom,
    encrypt_psarc,
)

ENTRY = Struct(
    "md5" / Bytes(16),
    "zindex" / Int32ub,
    "length" / BytesInteger(5),
    "offset" / BytesInteger(5),
)


class BOMAdapter(Adapter):
    """The BOM is encrypted together with the header only when the
    archive flags are set (PC/Mac); console archives keep it plaintext."""

    def _encode(self, obj, context, path):
        data = Struct(
            "entries" / ENTRY[context.n_entries], "zlength" / GreedyRange(Int16ub)
        ).build(obj)
        if context.flags == 0:
            return data
        return encrypt_bom(data)

    def _decode(self, obj, context, path):
        data = obj if context.flags == 0 else decrypt_bom(obj)
        return Struct(
            "entries" / ENTRY[context.n_entries], "zlength" / GreedyRange(Int16ub)
        ).parse(data)


VERSION = 65540
ENTRY_SIZE = ENTRY.sizeof()
BLOCK_SIZE = 2 ** 16
# header flags: 4 = encrypted BOM + AES-CTR sng containers (PC/Mac),
# 0 = plaintext BOM + plaintext sng containers (consoles)
ARCHIVE_FLAGS = 4

HEADER = Struct(
    "MAGIC" / Const(b"PSAR"),
    "VERSION" / Const(Int32ub.build(VERSION)),
    "COMPRESSION" / Const(b"zlib"),
    "header_size" / Int32ub,
    "ENTRY_SIZE" / Const(Int32ub.build(ENTRY_SIZE)),
    "n_entries" / Int32ub,
    "BLOCK_SIZE" / Const(Int32ub.build(BLOCK_SIZE)),
    "flags" / Int32ub,
    "bom" / BOMAdapter(Bytes(this.header_size - 32)),
)

# Platform families keyed by the directories used inside the archive.
# `be` platforms (Xbox 360, PS3) write the sng container header
# big-endian; `token` is the platform string inside aggregategraph.nt.
PLATFORMS = {
    "pc": dict(audio="audio/windows", bin="songs/bin/generic", flags=4,
               token="dx9", suffix="_p", be=False),
    "mac": dict(audio="audio/mac", bin="songs/bin/macos", flags=4,
                token="macos", suffix="_m", be=False),
    "xbox": dict(audio="audio/xbox360", bin="songs/bin/xbox360", flags=0,
                 token="xbox360", suffix="_x", be=True),
    "ps3": dict(audio="audio/ps3", bin="songs/bin/ps3", flags=0,
                token="ps3", suffix="", be=True),
    "ps4": dict(audio="audio/generic", bin="songs/bin/generic", flags=0,
                token="dx9", suffix="_ps4", be=False),
}

_AUDIO_DIRS = {p["audio"] for p in PLATFORMS.values()}
_BIN_DIRS = {p["bin"] for p in PLATFORMS.values()}


def detect_platform(content, flags=ARCHIVE_FLAGS):
    """Guess the platform of an archive from its entry paths and flags.

    PC and PS4 share the `songs/bin/generic` directory, so the archive
    flags break the tie."""
    audio = {os.path.dirname(name) for name in content if name.startswith("audio/")}
    bins = {
        os.path.dirname(name)
        for name in content
        if name.startswith("songs/bin/") and name != "songs/bin/aggregategraph.nt"
    }
    for key, p in PLATFORMS.items():
        if (audio and audio != {p["audio"]}) or (bins and bins != {p["bin"]}):
            continue
        if audio or bins:
            # pc and ps4 share songs/bin/generic; only flags break ties
            if not audio and p["bin"] == "songs/bin/generic":
                if bool(flags) != bool(p["flags"]):
                    continue
            return key
    return "pc" if flags else "ps4"


def read_entry(stream, n, bom):
    entry = bom.entries[n]
    stream.seek(entry.offset)
    zlength = bom.zlength[entry.zindex :]

    data = BytesIO()
    length = 0
    for z in zlength:
        if length == entry.length:
            break

        if z == 0:
            # stored block; zlength 0 marks full blocks as well as
            # partial tails from foreign archives -- clamp to the entry
            # size so a tail does not swallow the next entry's data
            chunk = stream.read(min(BLOCK_SIZE, entry.length - length))
        else:
            chunk = stream.read(z)
        try:
            chunk = zlib.decompress(chunk)
        except zlib.error:
            pass

        data.write(chunk)
        length += len(chunk)

    data = data.getvalue()
    assert len(data) == entry.length
    return data


def create_entry(name, data):
    zlength = []
    output = BytesIO()

    for i in range(0, len(data), BLOCK_SIZE):
        raw = data[i : i + BLOCK_SIZE]
        compressed = zlib.compress(raw, zlib.Z_BEST_COMPRESSION)
        if len(compressed) < len(raw):
            output.write(compressed)
            zlength.append(len(compressed))
        else:
            output.write(raw)
            # stored blocks record len(raw) % BLOCK_SIZE: 0 for full
            # blocks, the tail size for a partial last block
            zlength.append(len(raw) % BLOCK_SIZE)

    return {
        "md5": md5(name.encode()).digest() if name != "" else bytes(16),
        "zlength": zlength,
        "length": len(data),
        "data": output.getvalue(),
    }


def create_bom(entries):
    offset, zindex, zlength = 0, 0, []
    for entry in entries:
        entry["offset"] = offset
        entry["zindex"] = zindex
        offset += len(entry["data"])
        zindex += len(entry["zlength"])
        zlength += entry["zlength"]

    header_size = 32 + ENTRY_SIZE * len(entries) + 2 * len(zlength)
    for entry in entries:
        entry["offset"] += header_size

    return {"entries": entries, "zlength": zlength, "header_size": header_size}


def _map_path(name, src, dst):
    """Rewrite platform-specific directories inside an entry path."""
    for d, sub in (("audio", _AUDIO_DIRS), ("bin", _BIN_DIRS)):
        if name.startswith(src[d] + "/"):
            return name.replace(src[d], dst[d], 1)
        for other in sub:
            if other != src[d] and name.startswith(other + "/"):
                return name.replace(other, dst[d], 1)
    return name


def convert(filename, target=None):
    """Convert a PSARC between platforms (pc, mac, xbox, ps3, ps4).

    Rewrites entry paths and the platform tokens inside
    aggregategraph.nt and re-wraps the song data with the target's
    container (AES-CTR for PC/Mac, plaintext "4a" for consoles). Xbox
    360/PS3 chart data is NOT re-serialized: converting to/from those
    platforms produces the container/path layout only; big-endian chart
    rewriting and audio bank generation are out of scope.

    Returns the generated filename ("base<suffix>.psarc")."""
    with open(filename, "rb") as fh:
        # the archive flags sit at offset 28 of the 32-byte header
        head = fh.read(32)
        if len(head) < 32 or head[:4] != b"PSAR":
            raise ValueError("not a PSARC archive: %s" % filename)
        flags = int.from_bytes(head[28:32], "big")
        fh.seek(0)
        content = PSARC(crypto=flags != 0).parse_stream(fh)

    src_key = detect_platform(content, flags)
    src = PLATFORMS[src_key]
    if target is None:
        # classic pairing: _p -> mac, everything else -> pc
        target = "mac" if src_key == "pc" else "pc"
    dst = PLATFORMS[target]

    new_content = {}
    for name, data in content.items():
        if name.endswith("aggregategraph.nt"):
            for other in _AUDIO_DIRS:
                if other != dst["audio"]:
                    data = data.replace(other.encode(), dst["audio"].encode())
            for other in _BIN_DIRS:
                if other != dst["bin"]:
                    data = data.replace(other.encode(), dst["bin"].encode())
            if src["token"] != dst["token"]:
                data = data.replace(src["token"].encode(), dst["token"].encode())
        new_content[_map_path(name, src, dst)] = data

    outname = re.sub(r"(_p|_m|_x|_ps4)?\.psarc$", "", filename)
    outname += dst["suffix"] + ".psarc"
    if os.path.exists(outname) and os.path.abspath(outname) != os.path.abspath(filename):
        raise FileExistsError(outname)
    with open(outname, "wb") as fh:
        PSARC(crypto=dst["flags"] != 0, endian=">" if dst["be"] else "<").build_stream(
            new_content, fh
        )
    return outname


class PSARC(Construct):
    def __init__(self, crypto=True, endian="<"):
        self.crypto = crypto
        self.endian = endian
        super().__init__()

    def _parse(self, stream, context, path):
        header = HEADER.parse_stream(stream)
        listing, *entries = [
            read_entry(stream, i, header.bom) for i in range(header.n_entries)
        ]
        listing = listing.decode().splitlines()
        content = dict(zip(listing, entries))
        # always decoded per the archive's own flags
        return decrypt_psarc(content, flags=header.flags)

    def _build(self, content, stream, context, path):
        flags = ARCHIVE_FLAGS if self.crypto else 0
        content = encrypt_psarc(content, flags=flags, endian=self.endian)

        names = list(sorted(content.keys(), reverse=True))
        data = ["\n".join(names).encode()] + [content[k] for k in names]

        entries = [create_entry(n, e) for n, e in zip([""] + names, data)]
        bom = create_bom(entries)

        header = HEADER.build(
            {
                "header_size": bom["header_size"],
                "n_entries": len(entries),
                "flags": flags,
                "bom": bom,
            }
        )

        stream.write(header)
        for e in entries:
            stream.write(e["data"])

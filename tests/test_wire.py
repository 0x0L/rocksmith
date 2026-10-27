"""Wire conformance against bytes assembled here from the format
description with struct/zlib/hashlib/cryptography only. The other tests
write an archive with the library and read it back through the same
schema, so a wrong schema would agree with itself; these check both
directions against the layout official archives use, which the helpers
below spell out."""

import hashlib
import io
import itertools
import struct
import zlib
from pathlib import Path

import pytest
from cryptography.hazmat.decrepit.ciphers.modes import CFB
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from rocksmith.psarc import PSARC, convert
from test_main import run_cli

BLOCK = 1 << 16
ENTRY_SIZE = 30

# the published archive keys
ARC_KEY = bytes.fromhex(
    "C53DB23870A1A2F71CAE64061FDD0E1157309DC85204D4C5BFDF25090DF2572C"
)
ARC_IV = bytes.fromhex("E915AA018FEF71FC508132E4BB4CEB42")
WIN_KEY = bytes.fromhex(
    "CB648DF3D12A16BF71701414E69619EC171CCA5D2A142E3E59DE7ADDA18A3A30"
)
MAC_KEY = bytes.fromhex(
    "9821330E34B91F70D0A48CBD625993126970CEA09192C0E6CDA676CC9838289D"
)

CHART = b"CHART" * 5000
BANK = b"WWISEBANK" * 9000

# what each platform claims inside an archive: its directories, the token
# in aggregategraph.nt, the archive flags and the container byte order
LAYOUT = {
    "pc": dict(audio="audio/windows", bin="songs/bin/generic", token="dx9",
               flags=4, endian="<", suffix="_p", key=WIN_KEY),
    "mac": dict(audio="audio/mac", bin="songs/bin/macos", token="macos",
                flags=4, endian="<", suffix="_m", key=MAC_KEY),
    "xbox": dict(audio="audio/xbox360", bin="songs/bin/xbox360",
                 token="xbox360", flags=0, endian=">", suffix="_xbox"),
    "ps3": dict(audio="audio/ps3", bin="songs/bin/ps3", token="ps3",
                flags=0, endian=">", suffix="_ps3"),
    "ps4": dict(audio="audio/generic", bin="songs/bin/generic", token="dx9",
                flags=0, endian="<", suffix="_ps4"),
}


def cfb(data, decrypt=False):
    cipher = Cipher(algorithms.AES(ARC_KEY), CFB(ARC_IV))
    op = cipher.decryptor() if decrypt else cipher.encryptor()
    return op.update(data) + op.finalize()


def ctr(data, key=WIN_KEY, iv=bytes(16)):
    op = Cipher(algorithms.AES(key), modes.CTR(iv)).encryptor()
    return op.update(data) + op.finalize()


def container(data, endian="<"):
    """The plaintext "4a" container: magic, version 1, size, zlib."""
    return struct.pack(f"{endian}3I", 0x4A, 1, len(data)) + zlib.compress(
        data, zlib.Z_BEST_COMPRESSION
    )


def aes_container(data, key=WIN_KEY):
    """What PC/Mac store instead: version 3, the IV at offset 8, the
    CTR-encrypted size + zlib stream at 24, then 56 bytes of tail."""
    inner = struct.pack("<I", len(data)) + zlib.compress(
        data, zlib.Z_BEST_COMPRESSION
    )
    return struct.pack("<2I", 0x4A, 3) + bytes(16) + ctr(inner, key) + bytes(56)


def wrap(data, p):
    """The container bytes a platform stores a chart in."""
    return aes_container(data, p["key"]) if p["flags"] else container(
        data, p["endian"]
    )


def song(p, stored_chart):
    graph = (
        f'path="{p["audio"]}/t.wem" bin="{p["bin"]}/t.sng" tok={p["token"]}'
    ).encode()
    return {
        f"{p['bin']}/t.sng": stored_chart,
        f"{p['audio']}/t.wem": BANK,
        "songs/bin/aggregategraph.nt": graph,
    }


def assert_chart(data, p):
    """The stored chart for a platform: container framing and CHART."""
    if p["flags"]:
        assert data[:8] == struct.pack("<2I", 0x4A, 3)
        assert data[8:24] == bytes(16)  # the IV travels in the clear
        body = ctr(data[24:-56], p["key"])
        assert struct.unpack("<I", body[:4])[0] == len(CHART)
        assert zlib.decompress(body[4:]) == CHART
    else:
        assert data[:12] == struct.pack(
            f"{p['endian']}3I", 0x4A, 1, len(CHART)
        )
        assert zlib.decompress(data[12:]) == CHART


def pack(content, flags):
    """{entry: stored bytes} -> archive; record 0 holds the names."""
    names = list(content)
    payloads = ["\n".join(names).encode()] + [content[n] for n in names]

    blobs, starts, zindex, zl = bytearray(), [], [], []
    for data in payloads:
        starts.append(len(blobs))
        zindex.append(len(zl))
        for i in range(0, len(data), BLOCK):
            raw = data[i : i + BLOCK]
            zipped = zlib.compress(raw, zlib.Z_BEST_COMPRESSION)
            if len(zipped) < len(raw):
                blobs += zipped
                zl.append(len(zipped))
            else:
                blobs += raw
                zl.append(len(raw) % BLOCK)

    header_size = 32 + ENTRY_SIZE * len(payloads) + 2 * len(zl)
    hashes = [bytes(16)] + [hashlib.md5(n.encode()).digest() for n in names]
    table = b"".join(
        h
        + struct.pack(">I", zi)
        + len(d).to_bytes(5, "big")
        + (header_size + o).to_bytes(5, "big")
        for h, zi, d, o in zip(hashes, zindex, payloads, starts)
    ) + b"".join(struct.pack(">H", z) for z in zl)

    return (
        b"PSAR"
        + struct.pack(">I", 65540)
        + b"zlib"
        + struct.pack(">5I", header_size, ENTRY_SIZE, len(payloads), BLOCK, flags)
        + (cfb(table) if flags else table)
        + bytes(blobs)
    )


def toc(arc):
    """(flags, header_size, [(md5, zindex, length, offset)], zlib table)."""
    assert arc[:4] == b"PSAR" and arc[8:12] == b"zlib"
    version = struct.unpack(">I", arc[4:8])[0]
    header_size, entry_size, n, block, flags = struct.unpack(">5I", arc[12:32])
    assert (version, entry_size, block) == (65540, ENTRY_SIZE, BLOCK)
    table = arc[32:header_size]
    if flags:
        table = cfb(table, decrypt=True)
    rows = []
    for i in range(n):
        record = table[i * ENTRY_SIZE : (i + 1) * ENTRY_SIZE]
        rows.append(
            (
                record[:16],
                struct.unpack(">I", record[16:20])[0],
                int.from_bytes(record[20:25], "big"),
                int.from_bytes(record[25:30], "big"),
            )
        )
    zl = struct.unpack(
        ">%dH" % ((len(table) - n * ENTRY_SIZE) // 2), table[n * ENTRY_SIZE :]
    )
    return flags, header_size, rows, zl


def stored(arc):
    """(flags, {entry: bytes}) after block decompression and before any
    container is lifted, decoded without help from the library."""
    flags, _, rows, zl = toc(arc)
    payloads = []
    for _, zindex, length, offset in rows:
        out, off = bytearray(), offset
        for z in zl[zindex:]:
            if len(out) == length:
                break
            chunk = arc[off : off + (BLOCK if z == 0 else z)]
            off += len(chunk)
            try:
                chunk = zlib.decompress(chunk)
            except zlib.error:
                pass
            out += chunk
        assert len(out) == length
        payloads.append(bytes(out))
    return flags, dict(zip(payloads[0].decode().splitlines(), payloads[1:]))


def test_library_reads_plaintext_console_archive():
    arc = pack(song(LAYOUT["ps4"], container(CHART)), 0)
    content = PSARC().parse_stream(io.BytesIO(arc))
    assert content["songs/bin/generic/t.sng"] == CHART
    assert content["audio/generic/t.wem"] == BANK


def test_library_reads_big_endian_console_archive():
    arc = pack(song(LAYOUT["ps3"], container(CHART, ">")), 0)
    assert stored(arc)[1]["songs/bin/ps3/t.sng"][:4] == b"\x00\x00\x00\x4a"
    assert PSARC().parse_stream(io.BytesIO(arc))["songs/bin/ps3/t.sng"] == CHART


def test_library_reads_pc_archive():
    arc = pack(song(LAYOUT["pc"], aes_container(CHART)), 4)
    assert PSARC().parse_stream(io.BytesIO(arc))["songs/bin/generic/t.sng"] == CHART


def test_library_reads_mac_archive():
    arc = pack(song(LAYOUT["mac"], aes_container(CHART, MAC_KEY)), 4)
    assert PSARC().parse_stream(io.BytesIO(arc))["songs/bin/macos/t.sng"] == CHART


@pytest.mark.parametrize("crypto,flags", [(True, 4), (False, 0)])
def test_header_layout(crypto, flags):
    buf = io.BytesIO()
    PSARC(crypto=crypto).build_stream({"audio/windows/t.wem": b"x" * 10}, buf)
    arc = buf.getvalue()
    version = struct.unpack(">I", arc[4:8])[0]
    header_size, entry_size, n, block, got = struct.unpack(">5I", arc[12:32])
    assert (version, entry_size, block, got) == (65540, ENTRY_SIZE, BLOCK, flags)
    assert n == 2  # the entry plus the name manifest
    assert header_size == 32 + ENTRY_SIZE * n + 2 * len(toc(arc)[3])


def test_toc_hashes_the_filenames():
    buf = io.BytesIO()
    PSARC(crypto=False).build_stream(
        {"audio/windows/a.wem": CHART, "audio/windows/b.wem": CHART}, buf
    )
    arc = buf.getvalue()
    _, header_size, rows, _ = toc(arc)
    assert rows[0][0] == bytes(16)  # the manifest record carries no hash
    assert rows[0][3] == header_size  # ... and its data comes first
    assert {r[0] for r in rows[1:]} == {
        hashlib.md5(n.encode()).digest()
        for n in ("audio/windows/a.wem", "audio/windows/b.wem")
    }
    # the record length is the archived size; a bank is stored as given
    assert [r[2] for r in rows[1:]] == [len(CHART)] * 2


@pytest.mark.parametrize("platform", list(LAYOUT))
def test_library_output_carries_its_container(platform):
    p = LAYOUT[platform]
    buf = io.BytesIO()
    PSARC(crypto=bool(p["flags"]), endian=p["endian"]).build_stream(
        {f"{p['bin']}/t.sng": CHART}, buf
    )
    assert_chart(stored(buf.getvalue())[1][f"{p['bin']}/t.sng"], p)


@pytest.mark.parametrize("src,dst", list(itertools.product(LAYOUT, repeat=2)))
def test_convert_matrix_is_readable_without_the_library(tmp_path, src, dst):
    """Every source and target pair, judged off the bytes the converter
    wrote: flags, directories, graph tokens and container framing."""
    s, d = LAYOUT[src], LAYOUT[dst]
    name = tmp_path / f"song{s['suffix']}.psarc"
    name.write_bytes(pack(song(s, wrap(CHART, s)), s["flags"]))

    out = convert(str(name), dst)
    assert out == str(tmp_path / f"song{d['suffix']}.psarc")
    flags, raw = stored(Path(out).read_bytes())
    assert flags == d["flags"]
    assert set(raw) == {
        f"{d['bin']}/t.sng",
        f"{d['audio']}/t.wem",
        "songs/bin/aggregategraph.nt",
    }
    assert_chart(raw[f"{d['bin']}/t.sng"], d)
    assert raw["songs/bin/aggregategraph.nt"] == (
        f'path="{d["audio"]}/t.wem" bin="{d["bin"]}/t.sng" tok={d["token"]}'
    ).encode()
    assert raw[f"{d['audio']}/t.wem"] == BANK


def test_cli_repack_is_readable_without_the_library(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = LAYOUT["ps3"]
    (tmp_path / "song_ps3.psarc").write_bytes(pack(song(p, wrap(CHART, p)), 0))
    run_cli("--unpack", "song_ps3.psarc")
    run_cli("--no-crypto", "--pack", "song_ps3")

    flags, raw = stored((tmp_path / "song_ps3.psarc").read_bytes())
    assert flags == 0
    assert_chart(raw["songs/bin/ps3/t.sng"], p)

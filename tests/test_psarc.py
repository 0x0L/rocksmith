import io
import os

import pytest
from construct import Int32ub

from rocksmith import crypto
from rocksmith.psarc import (
    BLOCK_SIZE,
    HEADER,
    PSARC,
    PLATFORMS,
    _map_path,
    convert,
    create_bom,
    create_entry,
    detect_platform,
)


def build_archive(content, crypto_flag=True, endian="<"):
    buf = io.BytesIO()
    PSARC(crypto=crypto_flag, endian=endian).build_stream(content, buf)
    buf.seek(0)
    return buf


def test_roundtrip_small():
    content = {"a.txt": b"hello" * 10, "sub/b.bin": bytes(range(256))}
    back = PSARC(crypto=False).parse_stream(build_archive(content, False))
    assert back == content


def test_roundtrip_blocks():
    # 45 KiB of text compresses; 200 KiB of random data does not,
    # exercising compressed blocks and full stored blocks (zl 0).
    noise = os.urandom(200 * 1024)
    content = {"a.txt": b"lorem ipsum " * 4000, "n.bin": noise}
    back = PSARC(crypto=False).parse_stream(build_archive(content, False))
    assert back == content


def test_stored_block_marking():
    noise = os.urandom(3 * BLOCK_SIZE + 100)
    entry = create_entry("n.bin", noise)
    assert entry["zlength"][:3] == [0, 0, 0]  # full stored blocks
    assert entry["zlength"][3] == 100  # stored partial tail records size


def test_reader_accepts_zero_marked_partial_tail():
    # Archives may mark a stored partial final block with 0 instead of
    # its size; the reader must clamp to the declared entry length
    # rather than swallowing the next entry.
    noise = os.urandom(BLOCK_SIZE + 1000)
    listing = create_entry("", b"one\ntwo")
    e1, e2 = create_entry("one", noise), create_entry("two", b"second entry")
    e1["zlength"][-1] = 0  # store the 1000-byte tail as "0"

    bom = create_bom([listing, e1, e2])
    buf = io.BytesIO()
    buf.write(
        HEADER.build(
            {
                "header_size": bom["header_size"],
                "n_entries": 3,
                "flags": 0,
                "bom": bom,
            }
        )
    )
    buf.write(listing["data"])
    buf.write(e1["data"])
    buf.write(e2["data"])
    buf.seek(0)

    back = PSARC(crypto=False).parse_stream(buf)
    assert back == {"one": noise, "two": b"second entry"}


def test_console_flags_and_plaintext_toc():
    content = {"songs/bin/generic/t.sng": b"\x01\x02\x03chart", "l.txt": b"x"}
    arc = build_archive(content, False).read()
    assert Int32ub.parse(arc[28:32]) == 0
    back = PSARC(crypto=False).parse_stream(io.BytesIO(arc))
    assert back == content


def test_pc_flags_and_crypted_toc():
    content = {"songs/bin/generic/t.sng": b"chart"}
    arc = build_archive(content, True).read()
    assert Int32ub.parse(arc[28:32]) == 4
    back = PSARC(crypto=True).parse_stream(io.BytesIO(arc))
    assert back == content


def test_sng_ctr_roundtrip():
    raw = b"chart payload" * 100
    wrapped = crypto.encrypt_sng(raw, crypto.WIN_KEY)
    assert crypto.decrypt_sng(wrapped, crypto.WIN_KEY) == raw


def test_sng_console_wrap_roundtrip():
    raw = b"chart payload" * 100
    for endian in "<", ">":
        wrapped = crypto.wrap_sng_console(raw, endian)
        if endian == ">":
            assert wrapped[:4] == b"\x00\x00\x00\x4a"
        assert crypto.unwrap_sng_console(wrapped) == raw
    # payloads without the container magic pass through
    assert crypto.unwrap_sng_console(raw) == raw


def test_decrypt_psarc_flags_zero_unwraps():
    raw = b"chart"
    content = {
        "songs/bin/generic/t.sng": crypto.wrap_sng_console(raw),
        "audio/generic/t.wem": b"audio",
    }
    out = crypto.decrypt_psarc(content, flags=0)
    assert out["songs/bin/generic/t.sng"] == raw
    assert out["audio/generic/t.wem"] == b"audio"


def test_detect_platform():
    assert detect_platform({"audio/windows/a": b"", "songs/bin/generic/s": b""}) == "pc"
    assert detect_platform({"audio/mac/a": b"", "songs/bin/macos/s": b""}) == "mac"
    assert detect_platform({"audio/xbox360/a": b"", "songs/bin/xbox360/s": b""}) == "xbox"
    assert detect_platform({"audio/ps3/a": b"", "songs/bin/ps3/s": b""}) == "ps3"
    assert detect_platform({"audio/generic/a": b"", "songs/bin/generic/s": b""}) == "ps4"
    # flags alone can identify a console archive
    assert detect_platform({"songs/bin/generic/s": b""}, flags=0) == "ps4"
    # generic bins with encrypted flags resolve to pc, not ps4
    assert detect_platform({"songs/bin/generic/s": b""}, flags=4) == "pc"
    # content without recognizable dirs falls back on the flags
    assert detect_platform({"manifests/s/x": b""}, flags=4) == "pc"
    assert detect_platform({"manifests/s/x": b""}, flags=0) == "ps4"


def test_map_path():
    pc, ps4 = PLATFORMS["pc"], PLATFORMS["ps4"]
    assert _map_path("audio/windows/t.wem", pc, ps4) == "audio/generic/t.wem"
    assert _map_path("songs/bin/generic/t.sng", pc, ps4) == "songs/bin/generic/t.sng"
    # foreign dirs still collapse onto the destination
    assert _map_path("audio/mac/t.wem", pc, ps4) == "audio/generic/t.wem"


def make_song_content(platform="pc"):
    p = PLATFORMS[platform]
    chart = b"CHARTBYTES" * 100
    graph = (
        f'path="{p["audio"]}/t.wem" bin="{p["bin"]}/t.sng" tok={p["token"]}'
    ).encode()
    return p, chart, graph


@pytest.mark.parametrize("src,dst", [("pc", "ps4"), ("mac", "pc"), ("ps4", "pc")])
def test_convert_roundtrip(tmp_path, src, dst):
    p, chart, graph = make_song_content(src)
    name = tmp_path / f"song{p['suffix']}.psarc"
    content = {
        f"{p['bin']}/t.sng": chart,
        f"{p['audio']}/t.wem": b"AUDIOFILE",
        "scene.xml": b"<xml/>",
        "songs/bin/aggregategraph.nt": graph,
    }
    arc = build_archive(content, p["flags"] != 0)
    name.write_bytes(arc.read())

    out = convert(str(name), dst)
    q = PLATFORMS[dst]
    assert out.endswith(q["suffix"] + ".psarc")
    back = PSARC(crypto=q["flags"] != 0).parse_stream(open(out, "rb"))

    assert back[f"{q['bin']}/t.sng"] == chart
    assert back[f"{q['audio']}/t.wem"] == b"AUDIOFILE"
    assert back["scene.xml"] == b"<xml/>"
    nt = back["songs/bin/aggregategraph.nt"]
    assert q["audio"].encode() in nt and q["token"].encode() in nt
    for other in PLATFORMS.values():
        if other is not q:
            assert other["audio"].encode() not in nt


def test_convert_default_pairing(tmp_path):
    p, chart, graph = make_song_content("pc")
    name = tmp_path / "song_p.psarc"
    content = {f"{p['bin']}/t.sng": chart, f"{p['audio']}/t.wem": b"A"}
    name.write_bytes(build_archive(content, True).read())
    out = convert(str(name))
    assert out.endswith("song_m.psarc")


def test_convert_refuses_to_clobber_existing(tmp_path):
    # ps4->pc derives song_p.psarc; an unrelated archive of that name
    # must not be overwritten.
    p, chart, graph = make_song_content("ps4")
    src = tmp_path / "song_ps4.psarc"
    content = {f"{p['bin']}/t.sng": chart, f"{p['audio']}/t.wem": b"A"}
    src.write_bytes(build_archive(content, False).read())
    (tmp_path / "song_p.psarc").write_bytes(b"precious")
    with pytest.raises(FileExistsError):
        convert(str(src), "pc")
    assert (tmp_path / "song_p.psarc").read_bytes() == b"precious"
    # rewriting the file onto itself stays allowed
    assert convert(str(src), "ps4") == str(src)


def test_convert_rejects_non_psarc(tmp_path):
    bogus = tmp_path / "song_p.psarc"
    bogus.write_bytes(b"not an archive")
    with pytest.raises(ValueError):
        convert(str(bogus), "ps4")


@pytest.mark.skipif(not os.environ.get("ROCKSMITH_DLC"), reason="no sample archive")
def test_real_dlc_roundtrip():
    filename = os.environ["ROCKSMITH_DLC"]
    with open(filename, "rb") as fh:
        original = fh.read()
    content = PSARC().parse_stream(io.BytesIO(original))
    assert content

    rebuild = io.BytesIO()
    PSARC(crypto=True).build_stream(content, rebuild)
    assert PSARC().parse_stream(io.BytesIO(rebuild.getvalue())) == content

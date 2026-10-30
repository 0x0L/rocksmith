import io
import itertools
import os
from pathlib import Path

import pytest
from construct import Int32ub, Int32ul

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
    read_entry,
    read_source,
)


def build_archive(content, crypto_flag=True, endian="<"):
    buf = io.BytesIO()
    PSARC(crypto=crypto_flag, endian=endian).build_stream(content, buf)
    buf.seek(0)
    return buf


def raw_entries(arc):
    """(flags, {name: stored bytes}) straight off the archive: entry
    payloads after block decompression but before this library's
    decrypt/unwrap. This is what another tool sees."""
    buf = io.BytesIO(arc)
    hdr = HEADER.parse_stream(buf)
    entries = [read_entry(buf, i, hdr.bom) for i in range(hdr.n_entries)]
    return hdr.flags, dict(zip(entries[0].decode().splitlines(), entries[1:]))


def container_header(platform):
    """The bytes a stored chart starts with: the "4a" magic plus the
    container version, 3 for AES-CTR on PC/Mac, 1 for the plaintext
    container on consoles, in that platform's byte order."""
    u32 = Int32ul if platform["endian"] == "<" else Int32ub
    version = 3 if platform["flags"] else 1
    return u32.build(0x4A) + u32.build(version)


def make_song_content(platform="pc"):
    p = PLATFORMS[platform]
    chart = b"CHARTBYTES" * 100
    graph = (
        f'path="{p["audio"]}/t.wem" bin="{p["bin"]}/t.sng" tok={p["token"]}'
    ).encode()
    return p, chart, graph


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


def test_console_wrap_covers_charts_only():
    graph = b'<urn:uuid:1 bin="songs/bin/generic/t.sng" tok=dx9/>'
    content = {"songs/bin/generic/t.sng": b"CHART" * 40,
               "songs/bin/aggregategraph.nt": graph,
               "t_aggregategraph.nt": graph}
    packed = crypto.encrypt_psarc(content, flags=0)
    assert packed["songs/bin/generic/t.sng"][:4] == b"\x4a\x00\x00\x00"
    assert packed["songs/bin/aggregategraph.nt"] == graph
    assert packed["t_aggregategraph.nt"] == graph
    assert crypto.decrypt_psarc(packed, flags=0) == content


def test_decrypt_psarc_unwraps_charts_only():
    # unwrapping is keyed on the entry, not on the magic: a graph that an
    # earlier build of this library wrapped is not a chart and is handed
    # back untouched rather than silently rewritten
    graph = crypto.wrap_sng_console(b"<urn:uuid:1/>")
    chart = crypto.wrap_sng_console(b"CHART" * 40)
    out = crypto.decrypt_psarc(
        {"songs/bin/generic/t.sng": chart,
         "songs/bin/aggregategraph.nt": graph}, flags=0)
    assert out["songs/bin/generic/t.sng"] == b"CHART" * 40
    assert out["songs/bin/aggregategraph.nt"] == graph


def test_empty_chart_entry_stays_empty():
    # official DLC ships an arrangement entry with no bytes at all; it is
    # not a container, so it must be neither wrapped nor unwrapped
    cases = [(4, "songs/bin/generic/x.sng"), (0, "songs/bin/ps3/x.sng")]
    for flags, path in cases:
        content = {path: b"", "audio/windows/t.wem": b"bank"}
        packed = crypto.encrypt_psarc(content, flags=flags)
        assert packed[path] == b""
        assert crypto.decrypt_psarc(packed, flags=flags) == content
        arc = build_archive(content, flags != 0).read()
        assert raw_entries(arc)[1][path] == b""
        assert PSARC(crypto=flags != 0).parse(arc)[path] == b""


def test_detect_platform():
    assert detect_platform(
        {"audio/windows/a": b"", "songs/bin/generic/s": b""}) == "pc"
    assert detect_platform(
        {"audio/mac/a": b"", "songs/bin/macos/s": b""}) == "mac"
    assert detect_platform(
        {"audio/xbox360/a": b"", "songs/bin/xbox360/s": b""}) == "xbox"
    assert detect_platform(
        {"audio/ps3/a": b"", "songs/bin/ps3/s": b""}) == "ps3"
    assert detect_platform(
        {"audio/generic/a": b"", "songs/bin/generic/s": b""}) == "ps4"
    # flags alone can identify a console archive
    assert detect_platform({"songs/bin/generic/s": b""}, flags=0) == "ps4"
    # generic bins with encrypted flags resolve to pc, not ps4
    assert detect_platform({"songs/bin/generic/s": b""}, flags=4) == "pc"
    # content without recognizable dirs falls back on the flags, but a
    # fallback is not something to rewrite an archive against
    assert detect_platform({"manifests/s/x": b""}, flags=4) == "pc"
    assert detect_platform({"manifests/s/x": b""}, flags=0) == "ps4"
    with pytest.raises(ValueError):
        detect_platform({"manifests/s/x": b""}, flags=0, strict=True)


def test_detect_platform_accepts_names_only():
    # the platform probe reads the entry listing, never the payloads
    names = ["audio/ps3/t.wem", "songs/bin/ps3/t.sng", "songs/lyrics/x.xml"]
    assert detect_platform(names, flags=0) == "ps3"


def test_read_source_reports_platform_without_payloads(tmp_path):
    p, chart, graph = make_song_content("ps3")
    name = tmp_path / "song_ps3.psarc"
    content = {f"{p['bin']}/t.sng": chart, f"{p['audio']}/t.wem": b"A"}
    name.write_bytes(build_archive(content, p["flags"] != 0).read())
    assert read_source(str(name)) == (0, "ps3")


def test_map_path():
    pc, ps4 = PLATFORMS["pc"], PLATFORMS["ps4"]
    assert _map_path("audio/windows/t.wem", pc, ps4) == "audio/generic/t.wem"
    assert _map_path("songs/bin/generic/t.sng", pc, ps4) == "songs/bin/generic/t.sng"
    # foreign dirs still collapse onto the destination
    assert _map_path("audio/mac/t.wem", pc, ps4) == "audio/generic/t.wem"


@pytest.mark.parametrize("src,dst", list(itertools.product(PLATFORMS, repeat=2)))
def test_convert_matrix(tmp_path, src, dst):
    # five platforms into five: the paths, the graph tokens, the archive
    # flags and the container the target claims, payload still intact
    p, q = PLATFORMS[src], PLATFORMS[dst]
    name = tmp_path / f"song{p['suffix']}.psarc"
    chart = b"CHARTBYTES" * 100
    graph = (
        f'path="{p["audio"]}/t.wem" bin="{p["bin"]}/t.sng" tok={p["token"]}'
    ).encode()
    content = {
        f"{p['bin']}/t.sng": chart,
        f"{p["audio"]}/t.wem": b"AUDIOFILE",
        "scene.xml": b"<xml/>",
        "songs/bin/aggregategraph.nt": graph,
    }
    name.write_bytes(build_archive(content, p["flags"] != 0, p["endian"]).read())

    out = convert(str(name), dst)
    assert out == str(tmp_path / f"song{q['suffix']}.psarc")
    flags, stored = raw_entries(Path(out).read_bytes())
    assert flags == q["flags"]
    assert set(stored) == {
        f"{q['bin']}/t.sng", f"{q['audio']}/t.wem", "scene.xml",
        "songs/bin/aggregategraph.nt",
    }
    assert stored[f"{q['bin']}/t.sng"][:8] == container_header(q)
    assert stored["songs/bin/aggregategraph.nt"] == (
        f'path="{q["audio"]}/t.wem" bin="{q["bin"]}/t.sng" tok={q["token"]}'
    ).encode()
    assert detect_platform(list(stored), flags, strict=True) == dst

    back = PSARC(crypto=q["flags"] != 0).parse(Path(out).read_bytes())
    assert back[f"{q['bin']}/t.sng"] == chart
    assert back[f"{q['audio']}/t.wem"] == b"AUDIOFILE"
    assert back["scene.xml"] == b"<xml/>"


def test_convert_requires_target(tmp_path):
    p, chart, graph = make_song_content("pc")
    name = tmp_path / "song_p.psarc"
    content = {f"{p['bin']}/t.sng": chart, f"{p['audio']}/t.wem": b"A"}
    name.write_bytes(build_archive(content, True).read())
    with pytest.raises(TypeError):
        convert(str(name))


def test_convert_refuses_unidentifiable_source(tmp_path):
    # no audio/ or songs/bin/ directory: the flags would label this pc,
    # and rewriting against a label would move data to a platform the
    # archive never claimed
    name = tmp_path / "song_p.psarc"
    name.write_bytes(build_archive({"manifests/s/x": b"A"}, True).read())
    with pytest.raises(ValueError, match="cannot identify the platform"):
        convert(str(name), "mac")


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


@pytest.mark.parametrize("platform", ["xbox", "ps3", "ps4"])
def test_console_archive_stores_graph_raw(platform):
    # what the archive holds, not what this library reads back: the graph
    # stays a plain node graph and only the charts are container-wrapped
    p, chart, graph = make_song_content(platform)
    arc = build_archive(
        {f"{p['bin']}/t.sng": chart, f"{p['audio']}/t.wem": b"AUDIO",
         "songs/bin/aggregategraph.nt": graph, "t_aggregategraph.nt": graph},
        p["flags"] != 0, p["endian"]).read()
    flags, stored = raw_entries(arc)
    assert flags == 0
    assert stored["songs/bin/aggregategraph.nt"] == graph
    assert stored["t_aggregategraph.nt"] == graph
    assert stored[f"{p['bin']}/t.sng"][:8] == container_header(p)

import itertools
import subprocess
import sys

import pytest

from rocksmith.main import main
from rocksmith.psarc import PLATFORMS, PSARC
from rocksmith.sng import Song
from test_psarc import build_archive, container_header, make_song_content, raw_entries
from test_sng import minimal_song


def run_cli(*argv):
    old = sys.argv
    sys.argv = ["pyrocksmith", *argv]
    try:
        main()
    finally:
        sys.argv = old


def write_archive(path, platform, crypto, endian="<"):
    p, chart, graph = make_song_content(platform)
    content = {
        f"{p['bin']}/t.sng": chart,
        f"{p['audio']}/t.wem": b"A",
        f"{p['audio']}/u.wem": b"B",
        "t_aggregategraph.nt": graph,
    }
    path.write_bytes(build_archive(content, crypto, endian).read())
    return content


def test_cli_unpack_then_pack(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    content = write_archive(tmp_path / "song_p.psarc", "pc", True)
    run_cli("--unpack", "song_p.psarc")
    assert (tmp_path / "song_p" / "audio" / "windows" / "t.wem").read_bytes() == b"A"
    run_cli("--pack", "song_p")
    with open("song_p.psarc", "rb") as fh:
        assert PSARC(True).parse_stream(fh) == content


def test_cli_no_crypto_unpack_skips_aes_only(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    chart_path = "songs/bin/generic/t.sng"
    content = write_archive(tmp_path / "song_p.psarc", "pc", True)
    run_cli("--no-crypto", "--unpack", "song_p.psarc")
    _, stored = raw_entries((tmp_path / "song_p.psarc").read_bytes())
    on_disk = tmp_path.joinpath("song_p", chart_path).read_bytes()
    assert on_disk == stored[chart_path]  # still encrypted
    assert on_disk != content[chart_path]
    # a console container involves no keys, so --no-crypto lifts it
    content = write_archive(tmp_path / "song_ps4.psarc", "ps4", False)
    run_cli("--no-crypto", "--unpack", "song_ps4.psarc")
    on_disk = tmp_path.joinpath("song_ps4", chart_path).read_bytes()
    assert on_disk == content[chart_path]


@pytest.mark.parametrize("platform", ["ps4", "ps3"])
def test_cli_console_unpack_then_pack(tmp_path, monkeypatch, platform):
    monkeypatch.chdir(tmp_path)
    p = PLATFORMS[platform]
    name = f"song{p['suffix']}.psarc"
    content = write_archive(tmp_path / name, platform, False, p["endian"])
    run_cli("--unpack", name)
    run_cli("--no-crypto", "--pack", name[:-6])
    flags, stored = raw_entries((tmp_path / name).read_bytes())
    assert flags == 0
    # the reader sniffs endianness, so only the stored header catches this
    assert stored[f"{p['bin']}/t.sng"][:8] == container_header(p)
    assert stored["t_aggregategraph.nt"] == content["t_aggregategraph.nt"]


@pytest.mark.parametrize("src,dst", list(itertools.product(PLATFORMS, repeat=2)))
def test_cli_convert_matrix(tmp_path, monkeypatch, capsys, src, dst):
    monkeypatch.chdir(tmp_path)
    p, q = PLATFORMS[src], PLATFORMS[dst]
    source = f"song{p['suffix']}.psarc"
    write_archive(tmp_path / source, src, p["flags"] != 0, p["endian"])
    run_cli("--convert", source, "--platform", dst)

    out = capsys.readouterr().out.strip()
    assert out == f"song{q['suffix']}.psarc"
    flags, stored = raw_entries((tmp_path / out).read_bytes())
    assert flags == q["flags"]
    assert stored[f"{q['bin']}/t.sng"][:8] == container_header(q)
    assert f"{q['audio']}/t.wem" in stored


def test_cli_convert_requires_platform(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_archive(tmp_path / "song_ps4.psarc", "ps4", False)
    with pytest.raises(SystemExit):
        run_cli("--convert", "song_ps4.psarc")
    assert not (tmp_path / "song_p.psarc").exists()


def test_cli_convert_same_platform_warns(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    write_archive(tmp_path / "song_p.psarc", "pc", True)
    run_cli("--convert", "song_p.psarc", "--platform", "pc")
    captured = capsys.readouterr()
    assert "warning: song_p.psarc already contains pc data" in captured.err
    assert captured.out.strip() == "song_p.psarc"
    with open("song_p.psarc", "rb") as fh:
        assert "audio/windows/t.wem" in PSARC(True).parse_stream(fh)


def test_cli_convert_rejects_unknown_platform(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_archive(tmp_path / "song_ps4.psarc", "ps4", False)
    with pytest.raises(SystemExit):
        run_cli("--convert", "song_ps4.psarc", "--platform", "atari")


def test_cli_print_sng(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "t.sng").write_bytes(Song.build(minimal_song()))
    run_cli("--print-sng", "t.sng")
    out = capsys.readouterr().out
    assert '"beats"' in out
    assert '"_io"' not in out


def test_cli_without_arguments_prints_help(capsys):
    run_cli()
    assert "usage" in capsys.readouterr().out


def test_module_invocation():
    r = subprocess.run(
        [sys.executable, "-m", "rocksmith.main", "--help"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0
    assert "usage" in r.stdout

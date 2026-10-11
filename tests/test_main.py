import subprocess
import sys

import pytest

from rocksmith.main import main
from rocksmith.psarc import PSARC
from rocksmith.sng import Song
from test_psarc import build_archive, make_song_content
from test_sng import minimal_song


def run_cli(*argv):
    old = sys.argv
    sys.argv = ["pyrocksmith", *argv]
    try:
        main()
    finally:
        sys.argv = old


def write_archive(path, platform, crypto):
    p, chart, graph = make_song_content(platform)
    content = {
        f"{p['bin']}/t.sng": chart,
        f"{p['audio']}/t.wem": b"A",
        f"{p['audio']}/u.wem": b"B",
        "t_aggregategraph.nt": graph,
    }
    path.write_bytes(build_archive(content, crypto).read())
    return content


def test_cli_unpack_then_pack(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    content = write_archive(tmp_path / "song_p.psarc", "pc", True)
    run_cli("--unpack", "song_p.psarc")
    assert (tmp_path / "song_p" / "audio" / "windows" / "t.wem").read_bytes() == b"A"
    run_cli("--pack", "song_p")
    with open("song_p.psarc", "rb") as fh:
        assert PSARC(True).parse_stream(fh) == content


def test_cli_console_unpack_then_pack(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_archive(tmp_path / "song_ps4.psarc", "ps4", False)
    run_cli("--unpack", "song_ps4.psarc")
    run_cli("--no-crypto", "--pack", "song_ps4")
    with open("song_ps4.psarc", "rb") as fh:
        repacked = PSARC(False).parse_stream(fh)
    assert "songs/bin/generic/t.sng" in repacked
    assert repacked["t_aggregategraph.nt"] == make_song_content("ps4")[2]


def test_cli_convert(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    write_archive(tmp_path / "song_ps4.psarc", "ps4", False)
    run_cli("--convert", "song_ps4.psarc", "--platform", "pc")
    out = capsys.readouterr().out.strip()
    assert out == "song_p.psarc"
    with open(out, "rb") as fh:
        assert "audio/windows/t.wem" in PSARC(True).parse_stream(fh)


def test_cli_convert_default_pairing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    # console archive with no known suffix converts back to PC
    write_archive(tmp_path / "song_ps4.psarc", "ps4", False)
    run_cli("--convert", "song_ps4.psarc")
    assert capsys.readouterr().out.strip() == "song_p.psarc"
    # classic PC/Mac pairing from the filename suffix
    (tmp_path / "song_p.psarc").unlink()
    write_archive(tmp_path / "song_p.psarc", "pc", True)
    run_cli("--convert", "song_p.psarc")
    assert capsys.readouterr().out.strip() == "song_m.psarc"
    write_archive(tmp_path / "other_m.psarc", "mac", True)
    run_cli("--convert", "other_m.psarc")
    assert capsys.readouterr().out.strip() == "other_p.psarc"


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

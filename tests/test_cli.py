import pytest

from criba import __version__, cli


def test_version(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_parse_defaults(tmp_path) -> None:
    pdf = tmp_path / "libro.pdf"
    args = cli.parse_args([str(pdf)])
    assert args.pdf == pdf
    assert args.nivel == "normal"
    assert args.examen == "mixto"


def test_parse_rejects_bad_level(tmp_path) -> None:
    with pytest.raises(SystemExit):
        cli.parse_args([str(tmp_path / "x.pdf"), "--nivel", "enorme"])


def test_main_missing_file_returns_error(tmp_path, capsys, app_dirs) -> None:
    code = cli.main([str(tmp_path / "no-existe.pdf")])
    assert code == 2
    assert "No se ha encontrado" in capsys.readouterr().err

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


def test_main_protected_pdf_friendly_message(fx, capsys, app_dirs) -> None:
    assert cli.main([str(fx.protegido)]) == 2
    err = capsys.readouterr().err
    assert "protegido con contraseña" in err
    assert "Traceback" not in err


def test_main_prints_analysis(fx, capsys, app_dirs) -> None:
    assert cli.main([str(fx.con_indice)]) == 0
    out = capsys.readouterr().out
    assert "Asignatura: Biología general" in out
    assert "Capítulo 2. Genética" in out
    assert "fragmentos" in out


def test_thousands_use_spanish_separator() -> None:
    assert cli._miles(344668) == "344.668"
    assert cli._miles(7) == "7"

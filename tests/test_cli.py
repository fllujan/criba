import argparse

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
    assert cli.main([str(fx.con_indice), "--solo-analisis"]) == 0
    out = capsys.readouterr().out
    assert "Asignatura: Biología general" in out
    assert "Capítulo 2. Genética" in out
    assert "fragmentos" in out


def test_thousands_use_spanish_separator() -> None:
    assert cli._miles(344668) == "344.668"
    assert cli._miles(7) == "7"


def test_full_run_simulated(fx, tmp_path, capsys, app_dirs) -> None:
    out = tmp_path / "salida"
    code = cli.main(
        [str(fx.con_indice), "--simulado", "--si", "--salida", str(out), "--asignatura", "Bio"]
    )
    assert code == 0
    assert (out / "Bio - datos.json").is_file()
    assert "coste real" in capsys.readouterr().out


def test_declining_confirmation_processes_nothing(
    fx, tmp_path, monkeypatch, capsys, app_dirs
) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert cli.main([str(fx.con_indice), "--simulado", "--salida", str(tmp_path)]) == 0
    assert "No se ha procesado nada" in capsys.readouterr().out
    assert not list(tmp_path.glob("*.json"))


def test_missing_api_key_friendly_error(fx, tmp_path, capsys, app_dirs) -> None:
    assert cli.main([str(fx.con_indice), "--si", "--salida", str(tmp_path)]) == 2
    assert "Falta la clave de API" in capsys.readouterr().err


def test_ctrl_c_cancels_gracefully(fx, tmp_path, monkeypatch, capsys, app_dirs) -> None:
    def interrupt(*_a, **_k):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "run", interrupt)
    assert cli.main([str(fx.con_indice), "--simulado", "--si", "--salida", str(tmp_path)]) == 130
    assert "Lo procesado se ha guardado" in capsys.readouterr().err


def test_chapter_and_range_parsing() -> None:
    assert cli._chapters("3, 1,1") == (0, 2)
    assert cli._range("10–80") == (10, 80)
    with pytest.raises(argparse.ArgumentTypeError):
        cli._range("80-10")
    with pytest.raises(argparse.ArgumentTypeError):
        cli._chapters("a,b")
    assert cli._euros(1234.5) == "1.234,50"

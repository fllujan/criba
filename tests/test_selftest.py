"""Autocomprobación del ejecutable empaquetado (F6): la misma que corre el CI."""

import json
import os
from pathlib import Path

import keyring
import keyring.backend
import pytest
from keyring.backends import chainer, fail
from keyring.compat import properties

from criba import __main__ as entry
from criba.gui import selftest

pytestmark = pytest.mark.gui


def test_selftest_passes_and_writes_a_report(qapp, app_dirs, tmp_path) -> None:
    report = tmp_path / "informe.json"
    assert selftest.run(report) == 0
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["ok"] is True
    assert {c["name"] for c in data["checks"]} == {"pipeline", "interfaz", "llavero"}
    assert all(c["ok"] for c in data["checks"])


def test_selftest_never_touches_the_real_folders(qapp, app_dirs, tmp_path) -> None:
    selftest.run(tmp_path / "informe.json")
    assert os.environ["CRIBA_HOME"] == str(app_dirs)  # la restaura al terminar
    assert not (app_dirs / "out").exists()  # trabaja en su propia carpeta temporal


def test_a_failing_check_is_reported(qapp, app_dirs, tmp_path, monkeypatch) -> None:
    def broken() -> str:
        raise RuntimeError("sin llavero")

    monkeypatch.setattr(selftest, "check_keyring", broken)
    report = tmp_path / "informe.json"
    assert selftest.run(report) == 1
    data = json.loads(report.read_text(encoding="utf-8"))
    failed = [c for c in data["checks"] if not c["ok"]]
    assert data["ok"] is False
    assert [c["name"] for c in failed] == ["llavero"]
    assert "sin llavero" in failed[0]["detail"]


def test_entry_point_runs_the_selftest_when_asked(monkeypatch, tmp_path: Path) -> None:
    calls: list[Path] = []
    monkeypatch.setenv("CRIBA_SELFTEST", str(tmp_path / "r.json"))
    monkeypatch.setattr(selftest, "run", lambda p: calls.append(p) or 0)
    assert entry.main() == 0
    assert calls == [tmp_path / "r.json"]


class _Spy(keyring.backend.KeyringBackend):
    """Llavero que falla si alguien lo lee o lo escribe."""

    @properties.classproperty
    def priority(self):
        raise RuntimeError("solo para este test")

    def get_password(self, service, username):
        raise AssertionError("la autocomprobación ha leído el llavero")

    def set_password(self, service, username, password):
        raise AssertionError("la autocomprobación ha escrito en el llavero")

    def delete_password(self, service, username):
        raise AssertionError("la autocomprobación ha borrado del llavero")


def test_selftest_never_reads_the_saved_key(qapp, app_dirs, tmp_path) -> None:
    """En el Mac, leer la clave con otra firma abre un aviso del sistema y se queda esperando."""
    spy = _Spy()
    old = keyring.get_keyring()
    keyring.set_keyring(spy)
    try:
        report = tmp_path / "informe.json"
        assert selftest.run(report) == 0, report.read_text(encoding="utf-8")
        assert keyring.get_keyring() is spy  # restaurado
    finally:
        keyring.set_keyring(old)


def test_selftest_keyrings_stay_out_of_the_system_chain() -> None:

    names = [type(b).__name__ for b in chainer.ChainerBackend().backends]
    assert "_NoKeys" not in names
    assert "_Spy" not in names


def test_keyring_check_looks_inside_the_chain(monkeypatch) -> None:

    empty = chainer.ChainerBackend()
    monkeypatch.setattr(type(empty), "backends", property(lambda self: [fail.Keyring()]))
    monkeypatch.setattr(keyring, "get_keyring", lambda: empty)
    with pytest.raises(RuntimeError, match="sin llavero"):
        selftest.check_keyring()

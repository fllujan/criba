"""Caché SQLite de resultados de la IA (spec §6) y registro de trabajos (RNF-06, RF-18).

Cada resultado se guarda con una clave que combina el hash del PDF, el id del
fragmento, la versión del prompt, el modelo y las opciones que cambian la
respuesta. Si se cancela o falla, al repetir solo se pagan los fragmentos que faltan.
"""

import hashlib
import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from criba.core.cost import Usage

SCHEMA = """
CREATE TABLE IF NOT EXISTS results (
    key TEXT PRIMARY KEY,
    book_sha TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cache_write_tokens INTEGER NOT NULL,
    cache_read_tokens INTEGER NOT NULL,
    created TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS results_book ON results(book_sha);
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_sha TEXT NOT NULL,
    pdf_path TEXT NOT NULL,
    title TEXT NOT NULL,
    options TEXT NOT NULL,
    status TEXT NOT NULL,
    outputs TEXT NOT NULL DEFAULT '[]',
    cost_usd REAL NOT NULL DEFAULT 0,
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);
"""

JobStatus = str  # "running" | "done" | "cancelled" | "failed"


def make_key(*parts: object) -> str:
    """Clave estable a partir de las partes (hash SHA-256)."""
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Job:
    """Un libro procesado o en proceso."""

    id: int
    book_sha: str
    pdf_path: Path
    title: str
    options: dict[str, Any]
    status: JobStatus
    outputs: list[str]
    cost_usd: float
    created: str
    updated: str


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Cache:
    """Acceso seguro entre hilos a la base SQLite."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.executescript(SCHEMA)

    def close(self) -> None:
        """Cierra la conexión."""
        with self._lock:
            self._db.close()

    def __enter__(self) -> "Cache":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock, self._db:
            yield self._db

    # --- Resultados -------------------------------------------------------------

    def get(self, key: str) -> tuple[str, Usage] | None:
        """Devuelve (JSON, uso de tokens original) o ``None``."""
        with self._tx() as db:
            row = db.execute("SELECT * FROM results WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        usage = Usage(
            input=row["input_tokens"],
            output=row["output_tokens"],
            cache_write=row["cache_write_tokens"],
            cache_read=row["cache_read_tokens"],
        )
        return row["payload"], usage

    def has(self, key: str) -> bool:
        """Indica si la clave está en caché."""
        with self._tx() as db:
            return db.execute("SELECT 1 FROM results WHERE key = ?", (key,)).fetchone() is not None

    def put(
        self, key: str, *, book_sha: str, kind: str, payload: str, model: str, usage: Usage
    ) -> None:
        """Guarda un resultado (sobrescribe si ya existía)."""
        with self._tx() as db:
            db.execute(
                "INSERT OR REPLACE INTO results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    key,
                    book_sha,
                    kind,
                    payload,
                    model,
                    usage.input,
                    usage.output,
                    usage.cache_write,
                    usage.cache_read,
                    _now(),
                ),
            )

    def clear(self) -> None:
        """Borra toda la caché y el historial (Ajustes > Borrar caché)."""
        with self._tx() as db:
            db.execute("DELETE FROM results")
            db.execute("DELETE FROM jobs")
        with self._lock:
            self._db.execute("VACUUM")

    def count(self, book_sha: str | None = None) -> int:
        """Número de resultados guardados (de un libro o en total)."""
        with self._tx() as db:
            if book_sha is None:
                row = db.execute("SELECT COUNT(*) FROM results").fetchone()
            else:
                row = db.execute(
                    "SELECT COUNT(*) FROM results WHERE book_sha = ?", (book_sha,)
                ).fetchone()
        return int(row[0])

    # --- Trabajos ------------------------------------------------------------------

    def start_job(
        self, *, book_sha: str, pdf_path: Path, title: str, options: dict[str, Any]
    ) -> int:
        """Registra un trabajo en marcha y devuelve su id."""
        now = _now()
        with self._tx() as db:
            cur = db.execute(
                "INSERT INTO jobs (book_sha, pdf_path, title, options, status, created, updated)"
                " VALUES (?, ?, ?, ?, 'running', ?, ?)",
                (book_sha, str(pdf_path), title, json.dumps(options, sort_keys=True), now, now),
            )
            return int(cur.lastrowid or 0)

    def finish_job(
        self, job_id: int, status: JobStatus, *, outputs: list[str] | None = None, cost_usd: float
    ) -> None:
        """Marca el trabajo como terminado, cancelado o fallido."""
        with self._tx() as db:
            db.execute(
                "UPDATE jobs SET status = ?, outputs = ?, cost_usd = ?, updated = ? WHERE id = ?",
                (status, json.dumps(outputs or []), cost_usd, _now(), job_id),
            )

    def _job(self, row: sqlite3.Row) -> Job:
        return Job(
            id=row["id"],
            book_sha=row["book_sha"],
            pdf_path=Path(row["pdf_path"]),
            title=row["title"],
            options=json.loads(row["options"]),
            status=row["status"],
            outputs=json.loads(row["outputs"]),
            cost_usd=row["cost_usd"],
            created=row["created"],
            updated=row["updated"],
        )

    def jobs(self, status: JobStatus | None = None) -> list[Job]:
        """Trabajos, del más reciente al más antiguo."""
        with self._tx() as db:
            if status is None:
                rows = db.execute("SELECT * FROM jobs ORDER BY id DESC").fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM jobs WHERE status = ? ORDER BY id DESC", (status,)
                ).fetchall()
        return [self._job(r) for r in rows]

    def interrupted_jobs(self) -> list[Job]:
        """Trabajos que se quedaron a medias (para «Continuar donde lo dejaste»).

        Solo cuenta el último intento de cada libro con las mismas opciones: si se
        terminó después, ya no está a medias.
        """
        latest: dict[tuple[str, str], Job] = {}
        for job in self.jobs():  # del más reciente al más antiguo
            latest.setdefault((job.book_sha, json.dumps(job.options, sort_keys=True)), job)
        return [j for j in latest.values() if j.status in {"running", "cancelled"}]

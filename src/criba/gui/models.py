"""Modelos de lista para QML: capítulos detectados e historial."""

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import (
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
    Signal,
)

Index = QModelIndex | QPersistentModelIndex
ROLE = Qt.ItemDataRole.UserRole


@dataclass(slots=True)
class ChapterRow:
    """Un capítulo de la lista con casilla."""

    title: str
    first_page: int
    last_page: int
    checked: bool = True


class ChapterModel(QAbstractListModel):
    """Capítulos detectados con su casilla (RF-05)."""

    TITLE, FIRST, LAST, CHECKED = range(ROLE + 1, ROLE + 5)
    selectionChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[ChapterRow] = []

    def roleNames(self) -> dict[int, QByteArray]:
        """Nombres de los roles en QML."""
        return {
            self.TITLE: QByteArray(b"title"),
            self.FIRST: QByteArray(b"firstPage"),
            self.LAST: QByteArray(b"lastPage"),
            self.CHECKED: QByteArray(b"included"),
        }

    def rowCount(self, parent: Index = QModelIndex()) -> int:  # noqa: B008
        """Número de capítulos."""
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: Index, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Valor de un rol."""
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row = self._rows[index.row()]
        return {
            self.TITLE: row.title,
            Qt.ItemDataRole.DisplayRole: row.title,
            self.FIRST: row.first_page,
            self.LAST: row.last_page,
            self.CHECKED: row.checked,
        }.get(role)

    def reset(self, rows: list[ChapterRow]) -> None:
        """Sustituye la lista entera."""
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()
        self.selectionChanged.emit()

    def set_checked(self, row: int, checked: bool) -> None:
        """Marca o desmarca un capítulo."""
        if not 0 <= row < len(self._rows) or self._rows[row].checked == checked:
            return
        self._rows[row].checked = checked
        index = self.index(row)
        self.dataChanged.emit(index, index, [self.CHECKED])
        self.selectionChanged.emit()

    def set_all(self, checked: bool) -> None:
        """Marca o desmarca todos."""
        if not self._rows:
            return
        for r in self._rows:
            r.checked = checked
        self.dataChanged.emit(self.index(0), self.index(len(self._rows) - 1), [self.CHECKED])
        self.selectionChanged.emit()

    def checked_indices(self) -> list[int]:
        """Índices marcados."""
        return [i for i, r in enumerate(self._rows) if r.checked]

    def __len__(self) -> int:
        return len(self._rows)


@dataclass(slots=True)
class HistoryRow:
    """Un libro procesado."""

    job_id: int
    title: str
    date: str  # ISO 8601
    cost_usd: float
    summary: str
    outline: str
    data: str  # «datos.json» para regenerar sin coste
    available: bool  # los PDF siguen en su sitio


class HistoryModel(QAbstractListModel):
    """Historial de libros procesados (RF-18)."""

    JOB, TITLE, DATE, COST, SUMMARY, OUTLINE, DATA, AVAILABLE = range(ROLE + 1, ROLE + 9)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[HistoryRow] = []

    def roleNames(self) -> dict[int, QByteArray]:
        """Nombres de los roles en QML."""
        names = ("jobId", "title", "date", "costUsd", "summary", "outline", "dataFile", "available")
        return {
            role: QByteArray(name.encode())
            for role, name in zip(range(self.JOB, self.AVAILABLE + 1), names, strict=True)
        }

    def rowCount(self, parent: Index = QModelIndex()) -> int:  # noqa: B008
        """Número de libros."""
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: Index, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Valor de un rol."""
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        r = self._rows[index.row()]
        values = (r.job_id, r.title, r.date, r.cost_usd, r.summary, r.outline, r.data, r.available)
        if role == Qt.ItemDataRole.DisplayRole:
            return r.title
        if self.JOB <= role <= self.AVAILABLE:
            return values[role - self.JOB]
        return None

    def reset(self, rows: list[HistoryRow]) -> None:
        """Sustituye la lista entera."""
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def row(self, job_id: int) -> HistoryRow | None:
        """Fila de un trabajo."""
        return next((r for r in self._rows if r.job_id == job_id), None)

    def __len__(self) -> int:
        return len(self._rows)

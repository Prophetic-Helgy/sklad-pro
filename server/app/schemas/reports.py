"""Схемы отчётов (Фаза 5)."""
from pydantic import BaseModel


class ReportColumnOut(BaseModel):
    """Метаданные колонки — фронтенд строит таблицу по ним."""

    key: str
    title: str
    kind: str | None = None      # text | number | money | percent
    align: str | None = None     # left | right
    width: int | None = None


class ReportOut(BaseModel):
    """Страница отчёта (JSON). Строки — списки значений в порядке columns."""

    title: str
    period: str | None = None
    columns: list[ReportColumnOut]
    rows: list[list]
    totals: list | None = None
    total: int

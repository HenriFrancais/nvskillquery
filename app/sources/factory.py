"""Pick the data source from settings."""

from __future__ import annotations

from app.config import Settings
from app.sources.base import DataSource
from app.sources.demo import DemoSource
from app.sources.real import RealApiSource


def get_data_source(settings: Settings) -> DataSource:
    if settings.data_source == "demo":
        return DemoSource(settings.demo_data_dir)
    return RealApiSource(settings)

"""Fixture-only 검색 후보 검토. 실검색·독립 확인·게시 기능 없음."""

from .fixture_adapter import FixtureAdapter
from .service import run_preview
from .types import SearchRunConfig

__all__ = ["SearchRunConfig", "FixtureAdapter", "run_preview"]

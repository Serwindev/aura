"""Paths and loaders for repo-level config (rules/*.yaml)."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
RULES_DIR = REPO_ROOT / "rules"


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@dataclass(frozen=True)
class ValidationConfig:
    status: str
    ranges_default: dict[str, tuple[float, float]]
    ranges_by_type: dict[str, dict[str, tuple[float, float]]]
    danger_codes: frozenset[str]
    hbnc_days: frozenset[int] = field(default_factory=frozenset)
    hbyc_months: frozenset[int] = field(default_factory=frozenset)

    def range_for(self, visit_type: str | None, fld: str) -> tuple[float, float] | None:
        by_type = self.ranges_by_type.get(visit_type or "", {})
        return by_type.get(fld) or self.ranges_default.get(fld)


@lru_cache
def validation_config(rules_dir: Path = RULES_DIR) -> ValidationConfig:
    raw = load_yaml(rules_dir / "validation.yaml")
    codes = {c for group in raw["danger_signs"].values() for c in group}
    hbnc = load_yaml(rules_dir / "hbnc.yaml")
    hbyc = load_yaml(rules_dir / "hbyc.yaml")
    return ValidationConfig(
        status=raw["status"],
        ranges_default={k: tuple(v) for k, v in raw["ranges"]["default"].items()},
        ranges_by_type={t: {k: tuple(v) for k, v in r.items()}
                        for t, r in raw["ranges"].get("by_visit_type", {}).items()},
        danger_codes=frozenset(codes),
        hbnc_days=frozenset(v["day"] for v in hbnc["visits"]),
        hbyc_months=frozenset(v["month"] for v in hbyc["visits"]),
    )

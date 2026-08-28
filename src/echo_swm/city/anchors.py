from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from echo_swm.city.contracts import CityAnchorConfig, DistrictAnchor


@dataclass(frozen=True)
class ScaledDistrict:
    anchor: DistrictAnchor
    population_2025: float
    gdp_2025_100m: float


@dataclass(frozen=True)
class SuzhouAnchors:
    config: CityAnchorConfig
    districts: tuple[ScaledDistrict, ...]

    @property
    def population(self) -> float:
        return self.config.city_metrics["resident_population"].value

    @property
    def gdp_100m(self) -> float:
        return self.config.city_metrics["gdp"].value

    @property
    def district_ids(self) -> tuple[str, ...]:
        return tuple(item.anchor.district_id for item in self.districts)


def default_anchor_path() -> Path:
    return Path(__file__).resolve().parents[3] / "configs" / "cities" / "suzhou_2025.json"


def load_suzhou_anchors(path: Path | None = None) -> SuzhouAnchors:
    raw = (path or default_anchor_path()).read_text(encoding="utf-8")
    config = CityAnchorConfig.model_validate_json(raw)
    population_2024 = sum(district.population_2024 for district in config.districts)
    gdp_2024 = sum(district.gdp_2024_100m for district in config.districts)
    population_scale = config.city_metrics["resident_population"].value / population_2024
    gdp_scale = config.city_metrics["gdp"].value / gdp_2024
    districts = tuple(
        ScaledDistrict(
            anchor=district,
            population_2025=district.population_2024 * population_scale,
            gdp_2025_100m=district.gdp_2024_100m * gdp_scale,
        )
        for district in config.districts
    )
    return SuzhouAnchors(config=config, districts=districts)


def validate_anchor_totals(anchors: SuzhouAnchors) -> dict[str, float | bool]:
    district_population = sum(item.population_2025 for item in anchors.districts)
    district_gdp = sum(item.gdp_2025_100m for item in anchors.districts)
    return {
        "population_total": district_population,
        "population_matches": abs(district_population - anchors.population) < 1,
        "gdp_total_100m": district_gdp,
        "gdp_matches": abs(district_gdp - anchors.gdp_100m) < 0.01,
    }

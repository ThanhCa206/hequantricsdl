"""Dataset profile loader and schema representations."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

PROFILES_DIR = Path(__file__).resolve().parent / "profiles"


@dataclass
class DatasetProfile:
    name: str
    description: str
    num_customers: int
    num_products: int
    num_orders: int
    min_items_per_order: int = 1
    max_items_per_order: int = 5
    default_seed: int = 42
    distribution: str = "uniform"

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "num_customers": self.num_customers,
            "num_products": self.num_products,
            "num_orders": self.num_orders,
            "min_items_per_order": self.min_items_per_order,
            "max_items_per_order": self.max_items_per_order,
            "default_seed": self.default_seed,
            "distribution": self.distribution,
        }


def load_profile(name: str) -> DatasetProfile:
    """Load dataset profile by name (fixture, small, medium, large)."""
    file_path = PROFILES_DIR / f"{name.lower()}.json"
    if not file_path.exists():
        raise ValueError(
            f"Dataset profile '{name}' not found. Available profiles: fixture, small, medium, large"
        )
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return DatasetProfile(**data)


def list_profiles() -> Dict[str, DatasetProfile]:
    """List all available dataset profiles."""
    profiles = {}
    for p in ["fixture", "small", "medium", "large"]:
        file_path = PROFILES_DIR / f"{p}.json"
        if file_path.exists():
            profiles[p] = load_profile(p)
    return profiles

"""Configuration helpers (placeholder)."""

import json
from typing import Any, Dict


def load_json(path: str) -> Dict[str, Any]:
    """Load configuration from a JSON file.

    Args:
        path: The path to the JSON file.

    Returns:
        A dictionary containing the loaded configuration.
    """
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)

"""Make the HA-free helper module importable without a full HA test harness."""

import sys
from pathlib import Path

# weather_codes.py imports nothing from Home Assistant, so we can load it as a
# top-level module by putting the component directory on sys.path.
COMPONENT_DIR = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "meteo_tracker"
)
sys.path.insert(0, str(COMPONENT_DIR))

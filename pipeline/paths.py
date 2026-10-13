"""Where the project keeps its files.

The raw downloads and the database are tens of gigabytes, so they live outside
the code folder, in ~/nyc-hospital-data by default. Set the NYC_HOSPITAL_DATA
environment variable to use a different folder.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "data" / "registry.csv"

DATA = Path(os.environ.get("NYC_HOSPITAL_DATA", Path.home() / "nyc-hospital-data"))
RAW = DATA / "raw"
PARQUET = DATA / "parquet"
DATABASE = DATA / "prices.duckdb"

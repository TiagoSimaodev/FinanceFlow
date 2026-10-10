import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Config:
    DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
    VERCEL = os.environ.get("VERCEL") == "1"
    SECRET_KEY = os.environ.get("SECRET_KEY")
    AUTH_DISABLED = False
    DATABASE_PATH = Path(
        os.environ.get(
            "FINANCEFLOW_DATABASE",
            str(PROJECT_ROOT / "instance" / "financeflow.db"),
        )
    )

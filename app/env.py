from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def load_project_env() -> None:
    """
    Load environment variables from .env in common project locations.

    Priority (later calls can fill missing values, but won't overwrite by default):
    1) Current working directory
    2) Repository root (parent of app/)
    """
    load_dotenv(override=False)
    project_root = Path(__file__).resolve().parents[1]
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


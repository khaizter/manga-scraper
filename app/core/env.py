from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_env() -> None:
    load_dotenv(_PROJECT_ROOT / '.env')

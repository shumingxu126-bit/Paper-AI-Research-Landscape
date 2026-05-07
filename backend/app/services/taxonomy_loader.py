from pathlib import Path
import yaml
from app.core.settings import get_settings


def load_taxonomy() -> dict:
    settings = get_settings()
    path = Path(__file__).resolve().parent.parent.parent / settings.taxonomy_path
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

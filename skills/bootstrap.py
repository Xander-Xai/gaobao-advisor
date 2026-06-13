"""Pre-warm skill assets on startup."""
from pathlib import Path

from skills.service import SkillService

_service = SkillService(skills_dir=Path(__file__).parent)


def warmup_skill_assets() -> None:
    """Load all skill files into memory at startup."""
    _service.load_assets()
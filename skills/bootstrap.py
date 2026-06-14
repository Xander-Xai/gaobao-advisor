"""Pre-warm skill assets on startup."""

import logging
from pathlib import Path

from skills.service import SkillService

logger = logging.getLogger(__name__)

_service = SkillService(skills_dir=Path(__file__).parent)


def warmup_skill_assets() -> None:
    """Load all skill files into memory at startup."""
    try:
        _service.load_assets()
    except Exception as e:
        logger.warning(f"Skill assets warmup failed: {e}")

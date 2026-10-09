"""Imports every model module so all tables are registered on Base.metadata.

Alembic and the tests import this; add each new feature's models here.
"""

from app.core import models as core_models
from app.rounder import models as rounder_models
from app.scraper import models as scraper_models
from app.tracker import models as tracker_models

__all__ = ["core_models", "rounder_models", "scraper_models", "tracker_models"]

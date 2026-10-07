"""Imports every model module so all tables are registered on Base.metadata.

Alembic and the tests import this; add each new feature's models here.
"""

from app.core import models as core_models
from app.tracker import models as tracker_models

__all__ = ["core_models", "tracker_models"]

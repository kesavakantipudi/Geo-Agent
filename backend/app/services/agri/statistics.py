"""Legacy import shim for masked statistics (moved to geospatial.statistics).

``statistics`` lives in the shared ``geospatial`` package so every derived
intelligence service (agriculture now, water next) uses one implementation.
This module keeps ``from app.services.agri.statistics import ...`` working.
"""

from app.services.geospatial.statistics import describe, valid_fraction

__all__ = ["describe", "valid_fraction"]

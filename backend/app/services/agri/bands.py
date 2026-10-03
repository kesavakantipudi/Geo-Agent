"""Legacy import shim for band-role resolution (moved to geospatial.bands).

``bands`` lives in the shared ``geospatial`` package so every derived
intelligence service (agriculture now, water next) uses one mapping.
"""

from app.services.geospatial.bands import resolve_band_keys

__all__ = ["resolve_band_keys"]

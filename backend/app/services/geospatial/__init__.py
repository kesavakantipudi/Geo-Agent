"""Shared geospatial raster primitives for derived intelligence services.

Phase 6A introduces two layers on top of the satellite asset retrieval
pipeline:

- ``geospatial``: provider-independent low-level raster helpers (windowed
  reads, AOI masking, reprojection, pixel area) shared by every intelligence
  service (agriculture now, water/change/historical later);
- ``agri`` (agricultural intelligence): the first consumer, computing
  deterministic spectral indices (NDVI), masked statistics, and documented
  heuristic vegetation-condition tiers from retrieved Sentinel-2 assets.

Nothing in this package ever fabricates measurements: an index is produced
only when the required band assets are locally retrievable, any condition
that prevents a computation is returned as an explicit "unavailable" state
with the underlying reason preserved.
"""

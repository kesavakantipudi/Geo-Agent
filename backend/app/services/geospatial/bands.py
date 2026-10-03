"""Semantic band-role -> asset-key resolution per provider (shared Phase 6 core).

Index specifications declare *semantic* band roles (red/nir/green, cloud_mask).
This module maps those roles to the concrete asset keys each satellite provider
exposes for its scenes, so intelligence services stay provider-independent. A
provider with no registered mapping for an index simply cannot be analyzed and
surfaces an explicit "unsupported provider / band mapping" unavailable state.
"""

from __future__ import annotations

# index name -> provider -> {role: asset_key}
_BAND_ROLE_KEYS: dict[str, dict[str, dict[str, str]]] = {
    "ndvi": {
        # Sentinel-2 Level-2A on Microsoft Planetary Computer and on
        # Copernicus Data Space Ecosystem both key bands as B04/B08/SCL.
        "planetary-computer": {"red": "B04", "nir": "B08", "cloud_mask": "SCL"},
        "cdse": {"red": "B04", "nir": "B08", "cloud_mask": "SCL"},
    },
    "ndwi": {
        # Water index uses GREEN = B03 and NIR = B08 (same L2A band keys).
        "planetary-computer": {"green": "B03", "nir": "B08", "cloud_mask": "SCL"},
        "cdse": {"green": "B03", "nir": "B08", "cloud_mask": "SCL"},
    },
}


def resolve_band_keys(provider: str, index_name: str) -> dict[str, str] | None:
    """Return the {role -> asset key} mapping for a provider+index, else None."""
    return (_BAND_ROLE_KEYS.get(index_name) or {}).get(provider)

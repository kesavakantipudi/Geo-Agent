"""Change-mask PNG encoding (Phase 6D).

Change class masks are small ``uint8`` grids. They are encoded to a base64 PNG
data URI with the ``rasterio`` PNG driver (``nodata=255``) so the frontend can
render them as an ``ImageOverlay`` on the analysis map without any extra
dependencies. The mask classes and the grid footprint are carried alongside the
image in the API response, never inferred from colour band values.
"""

from __future__ import annotations

import base64

import numpy as np
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

MASK_MIME = "image/png;base64"


def encode_mask_png(mask: np.ndarray) -> str:
    """Encode a uint8 class mask as a base64 PNG data URI."""
    mask = np.asarray(mask, dtype=np.uint8)
    height, width = mask.shape[-2:]
    with MemoryFile() as memfile:
        with memfile.open(
            driver="PNG",
            width=width,
            height=height,
            count=1,
            dtype="uint8",
            nodata=255,
            transform=from_origin(0.0, 0.0, 1.0, 1.0),
        ) as dataset:
            dataset.write(mask, 1)
        data = memfile.read()
    encoded = base64.b64encode(bytes(data)).decode("ascii")
    return f"data:{MASK_MIME},{encoded}"

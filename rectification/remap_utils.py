"""Utilities for OpenCV remap operations."""

from __future__ import annotations

from typing import Tuple

import cv2
import numpy as np


def apply_remap(
    image: np.ndarray,
    map_x: np.ndarray,
    map_y: np.ndarray,
    interpolation: int = cv2.INTER_LINEAR,
    border_mode: int = cv2.BORDER_CONSTANT,
) -> np.ndarray:
    """Apply precomputed remap matrices to an image."""
    return cv2.remap(image, map_x, map_y, interpolation=interpolation, borderMode=border_mode)


def map_dtype_pair() -> Tuple[int, int]:
    """Recommended map types for cv2.initUndistortRectifyMap."""
    return cv2.CV_32FC1, cv2.CV_32FC1

"""Monocular undistortion helpers."""

from __future__ import annotations

from typing import Tuple

import cv2
import numpy as np

from .remap_utils import apply_remap


def build_undistort_map(
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray,
    image_size: Tuple[int, int],
    alpha: float = 0.0,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build undistortion maps for a single camera.

    image_size is (width, height).
    """
    width, height = image_size
    new_camera_matrix, _ = cv2.getOptimalNewCameraMatrix(
        camera_matrix,
        dist_coeffs,
        (width, height),
        alpha,
        (width, height),
    )
    map_x, map_y = cv2.initUndistortRectifyMap(
        camera_matrix,
        dist_coeffs,
        None,
        new_camera_matrix,
        (width, height),
        cv2.CV_32FC1,
    )
    return map_x, map_y, new_camera_matrix


def rectify_image(image: np.ndarray, map_x: np.ndarray, map_y: np.ndarray) -> np.ndarray:
    """Undistort one image with precomputed maps."""
    return apply_remap(image, map_x, map_y)

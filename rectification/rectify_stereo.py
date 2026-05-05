"""Stereo rectification helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import cv2
import numpy as np

from .remap_utils import apply_remap


@dataclass
class StereoMaps:
    left_map_x: np.ndarray
    left_map_y: np.ndarray
    right_map_x: np.ndarray
    right_map_y: np.ndarray
    q_matrix: np.ndarray


def build_stereo_rectification(
    camera_matrix_left: np.ndarray,
    dist_left: np.ndarray,
    camera_matrix_right: np.ndarray,
    dist_right: np.ndarray,
    rotation: np.ndarray,
    translation: np.ndarray,
    image_size: Tuple[int, int],
    alpha: float = 0.0,
) -> StereoMaps:
    """Compute stereo rectification transforms and remap matrices."""
    width, height = image_size
    r1, r2, p1, p2, q, _, _ = cv2.stereoRectify(
        camera_matrix_left,
        dist_left,
        camera_matrix_right,
        dist_right,
        (width, height),
        rotation,
        translation,
        alpha=alpha,
    )

    left_map_x, left_map_y = cv2.initUndistortRectifyMap(
        camera_matrix_left,
        dist_left,
        r1,
        p1,
        (width, height),
        cv2.CV_32FC1,
    )
    right_map_x, right_map_y = cv2.initUndistortRectifyMap(
        camera_matrix_right,
        dist_right,
        r2,
        p2,
        (width, height),
        cv2.CV_32FC1,
    )

    return StereoMaps(left_map_x, left_map_y, right_map_x, right_map_y, q)


def rectify_stereo_pair(
    left_image: np.ndarray,
    right_image: np.ndarray,
    maps: StereoMaps,
) -> Tuple[np.ndarray, np.ndarray]:
    """Rectify left and right images with precomputed stereo maps."""
    left_rect = apply_remap(left_image, maps.left_map_x, maps.left_map_y)
    right_rect = apply_remap(right_image, maps.right_map_x, maps.right_map_y)
    return left_rect, right_rect

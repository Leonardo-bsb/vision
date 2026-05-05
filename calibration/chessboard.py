import cv2
import numpy as np


def construir_pontos_objeto(rows, cols, square_size):
    """Constroi grade 3D plana de cantos do tabuleiro."""
    objp = np.zeros((rows * cols, 3), np.float32)
    objp[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2)
    return objp * square_size


def detectar_cantos_estereo(img_l, img_r, rows, cols, criteria):
    """Detecta e refina cantos em um par de imagens; retorna None em falha."""
    gray_l = cv2.cvtColor(img_l, cv2.COLOR_BGR2GRAY)
    gray_r = cv2.cvtColor(img_r, cv2.COLOR_BGR2GRAY)

    ret_l, corners_l = cv2.findChessboardCorners(gray_l, (cols, rows), None)
    ret_r, corners_r = cv2.findChessboardCorners(gray_r, (cols, rows), None)

    if not (ret_l and ret_r):
        return None

    corners_l2 = cv2.cornerSubPix(gray_l, corners_l, (11, 11), (-1, -1), criteria)
    corners_r2 = cv2.cornerSubPix(gray_r, corners_r, (11, 11), (-1, -1), criteria)
    return corners_l2, corners_r2

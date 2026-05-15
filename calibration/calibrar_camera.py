"""
Script de calibracao monocular com imagens de tabuleiro de xadrez.

Modo de uso:
    python3 calibration/calibrar_camera.py DIR_FOTOS [opcoes]

Exemplos:
    python3 calibration/calibrar_camera.py calibration/frames/esquerda
    python3 calibration/calibrar_camera.py calibration/frames/esquerda --rows 9 --cols 6 --size 5.0 --out calibration/npz_files/camera_esq.npz

Observacao:
    rows e cols sao o numero de cantos internos do tabuleiro, nao o numero de quadrados.
"""

import argparse
import glob
import os

import cv2
import numpy as np


def calibrar_camera(dir_fotos, rows=9, cols=6, square_size_cm=5.0, output_file="calibracao_camera.npz"):
    """Calibra uma camera unica usando imagens de tabuleiro e salva matriz/distorsao em .npz."""
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-5)

    # Gera os pontos 3D ideais do padrao no plano Z=0 (referencial do tabuleiro).
    objp = np.zeros((rows * cols, 3), np.float32)
    objp[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2)
    objp = objp * square_size_cm

    objpoints = []
    imgpoints = []

    padroes = ["*.JPG", "*.jpg", "*.PNG", "*.png"]
    imagens = []
    for padrao in padroes:
        imagens.extend(glob.glob(os.path.join(dir_fotos, padrao)))
    imagens = sorted(imagens)

    print(f"Encontradas {len(imagens)} imagens para calibracao.")

    if not imagens:
        raise RuntimeError("Nenhuma imagem encontrada. Verifique a pasta e a extensao dos arquivos.")

    img_shape = None

    for img_path in imagens:
        img = cv2.imread(img_path)
        if img is None:
            print(f" - Erro ao ler: {os.path.basename(img_path)}")
            continue

        if img_shape is None:
            img_shape = (img.shape[1], img.shape[0])

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        ret, corners = cv2.findChessboardCorners(gray, (cols, rows), None)

        if ret:
            # Refina os cantos para melhorar precisao da calibracao.
            objpoints.append(objp)
            corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            imgpoints.append(corners2)
            print(f" + Tabuleiro detectado em: {os.path.basename(img_path)}")
        else:
            print(f" - Falha na deteccao em: {os.path.basename(img_path)}")

    if not objpoints:
        raise RuntimeError(
            "Nenhum tabuleiro detectado. Verifique rows/cols e a qualidade das imagens."
        )

    print("Calibrando camera... (isso pode demorar)")
    rms, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, img_shape, None, None)

    # Calcula erro medio por ponto reprojetando os pontos 3D nas imagens.
    total_error = 0.0
    total_points = 0
    for index in range(len(objpoints)):
        imgpoints2, _ = cv2.projectPoints(objpoints[index], rvecs[index], tvecs[index], mtx, dist)
        err = cv2.norm(imgpoints[index], imgpoints2, cv2.NORM_L2)
        total_error += err ** 2
        total_points += len(imgpoints2)

    mean_error = np.sqrt(total_error / total_points)

    out_dir = os.path.dirname(output_file)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    np.savez(
        output_file,
        camera_matrix=mtx,
        dist_coeffs=dist,
        img_shape=img_shape,
        rms=rms,
        mean_error=mean_error,
    )

    print(f"Erro de reprojecao RMS (cv2.calibrateCamera): {rms:.4f}")
    print(f"Erro medio por ponto: {mean_error:.4f} pixels")
    print(f"Dados salvos em '{output_file}'")

    return {
        "rms": float(rms),
        "mean_error": float(mean_error),
        "images_used": int(len(objpoints)),
        "images_found": int(len(imagens)),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calibracao mono de uma camera com tabuleiro.")
    parser.add_argument("dir_fotos", nargs="?", default="tabuleiro", help="Pasta com as imagens do tabuleiro")
    parser.add_argument("--rows", type=int, default=9, help="Numero de cantos internos verticais")
    parser.add_argument("--cols", type=int, default=6, help="Numero de cantos internos horizontais")
    parser.add_argument("--size", type=float, default=5.0, help="Tamanho do quadrado em cm")
    parser.add_argument("--out", default="calibracao_camera.npz", help="Arquivo de saida .npz")
    args = parser.parse_args()

    if not os.path.exists(args.dir_fotos):
        raise SystemExit(f"Pasta nao encontrada: {args.dir_fotos}")

    try:
        calibrar_camera(
            dir_fotos=args.dir_fotos,
            rows=args.rows,
            cols=args.cols,
            square_size_cm=args.size,
            output_file=args.out,
        )
    except RuntimeError as exc:
        raise SystemExit(f"Erro: {exc}")
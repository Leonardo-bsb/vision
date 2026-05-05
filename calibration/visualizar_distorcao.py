import argparse
import os

import cv2
import numpy as np


def visualizar_correcao(img_path, calib_file="calibracao_camera.npz", output_img="comparacao_distorcao.jpg"):
    """Gera comparacao lado a lado entre imagem original e corrigida."""
    if not os.path.exists(calib_file):
        raise RuntimeError(f"Arquivo de calibracao nao encontrado: '{calib_file}'")
    if not os.path.exists(img_path):
        raise RuntimeError(f"Imagem nao encontrada: '{img_path}'")

    with np.load(calib_file) as data:
        if "camera_matrix" in data:
            mtx = data["camera_matrix"]
            dist = data["dist_coeffs"]
        elif "mtx_l" in data:
            print("Detectado arquivo de calibracao estereo. Usando camera esquerda.")
            mtx = data["mtx_l"]
            dist = data["dist_l"]
        else:
            raise RuntimeError("Chaves de calibracao nao encontradas no arquivo .npz")

    print(f"Lendo imagem: {img_path}")
    print("Aplicando correcao de distorcao...")

    img = cv2.imread(img_path)
    if img is None:
        raise RuntimeError(f"Falha ao ler imagem: '{img_path}'")

    h, w = img.shape[:2]
    newcameramtx, _ = cv2.getOptimalNewCameraMatrix(mtx, dist, (w, h), 1, (w, h))
    dst = cv2.undistort(img, mtx, dist, None, newcameramtx)

    scale = 0.4
    img_s = cv2.resize(img, None, fx=scale, fy=scale)
    dst_s = cv2.resize(dst, None, fx=scale, fy=scale)

    cv2.putText(img_s, "Original (Distorcida)", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    cv2.putText(dst_s, "Corrigida (Retificada)", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    combined = np.hstack((img_s, dst_s))
    cv2.imwrite(output_img, combined)
    print(f"Imagem comparativa salva em: {output_img}")

    try:
        cv2.imshow("Comparacao: Original vs Calibrada", combined)
        print("Pressione qualquer tecla na janela para fechar...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    except cv2.error:
        pass

    return output_img


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualiza correcao de distorcao com arquivo de calibracao.")
    parser.add_argument("imagem", help="Imagem a ser corrigida")
    parser.add_argument("calibracao", nargs="?", default="calibracao_camera.npz", help="Arquivo .npz de calibracao")
    parser.add_argument("--out", default="comparacao_distorcao.jpg", help="Imagem comparativa de saida")
    args = parser.parse_args()

    try:
        visualizar_correcao(args.imagem, args.calibracao, args.out)
    except RuntimeError as exc:
        raise SystemExit(f"Erro: {exc}")
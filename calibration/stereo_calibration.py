import glob
import os
import time

import cv2
import numpy as np

from .chessboard import construir_pontos_objeto, detectar_cantos_estereo


def inferir_par_direita(img_l_path):
    """Infere caminho da imagem direita a partir da esquerda."""
    head, tail = os.path.split(img_l_path)
    stem, ext = os.path.splitext(tail)

    if stem.endswith("_L"):
        return os.path.join(head, stem[:-2] + "_R" + ext)
    if stem.endswith("-L"):
        return os.path.join(head, stem[:-2] + "-R" + ext)
    if stem.startswith("L_"):
        return os.path.join(head, "R_" + stem[2:] + ext)
    if stem.endswith("L") and (len(stem) == 1 or stem[-2] in "_-"):
        return os.path.join(head, stem[:-1] + "R" + ext)
    return None


def calcular_erros_reprojecao(objpoints, imgpoints, rvecs, tvecs, mtx, dist):
    """Calcula erro medio de reprojecao por imagem."""
    errors = []
    for i in range(len(objpoints)):
        imgpoints2, _ = cv2.projectPoints(objpoints[i], rvecs[i], tvecs[i], mtx, dist)
        error = cv2.norm(imgpoints[i], imgpoints2, cv2.NORM_L2) / np.sqrt(len(imgpoints2))
        errors.append(error)
    return np.array(errors)


def _listar_pares_validos(dir_fotos):
    all_left = sorted(
        glob.glob(os.path.join(dir_fotos, "*L*.png"))
        + glob.glob(os.path.join(dir_fotos, "*L*.jpg"))
        + glob.glob(os.path.join(dir_fotos, "*L*.PNG"))
        + glob.glob(os.path.join(dir_fotos, "*L*.JPG"))
    )

    valid_pairs = []
    for img_l_path in all_left:
        img_r_path = inferir_par_direita(img_l_path)
        if img_r_path and os.path.exists(img_r_path):
            valid_pairs.append((img_l_path, img_r_path))
    return valid_pairs


def calibrar_stereo_robusta(
    dir_fotos,
    rows=9,
    cols=6,
    square_size=5.0,
    output_file="dados_calibracao.npz",
    max_pairs=100,
    salvar_pares_ruins_path=None,
    top_n_piores=5,
    unidade_baseline="cm",
    rectify_alpha=None,
):
    """Calibracao estereo robusta com validacoes e metricas de qualidade."""
    if not os.path.exists(dir_fotos):
        raise RuntimeError(f"Pasta nao encontrada: '{dir_fotos}'")

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-4)
    objp = construir_pontos_objeto(rows, cols, square_size)

    objpoints = []
    imgpoints_l = []
    imgpoints_r = []

    valid_pairs = _listar_pares_validos(dir_fotos)
    if not valid_pairs:
        raise RuntimeError(
            "Nenhum par L/R encontrado. Padroes esperados: "
            "*_L.jpg/*_R.jpg, *_L.png/*_R.png, L_*.jpg/R_*.jpg, xxx-L.jpg/xxx-R.jpg"
        )

    print(f"Encontrados {len(valid_pairs)} pares de imagens validos para calibracao.")

    if max_pairs is not None and len(valid_pairs) > max_pairs:
        print(f"AVISO: Muitos pares ({len(valid_pairs)}). Usando amostra de {max_pairs} para acelerar.")
        indices = np.linspace(0, len(valid_pairs) - 1, max_pairs, dtype=int)
        valid_pairs = [valid_pairs[i] for i in indices]

    img_shape = None
    kept_pairs = []
    bad_pairs = []

    t0_det = time.perf_counter()
    processed = 0
    detected = 0

    for img_l_path, img_r_path in valid_pairs:
        processed += 1
        img_l = cv2.imread(img_l_path)
        img_r = cv2.imread(img_r_path)

        if img_l is None or img_r is None:
            print(f" - Erro ao ler par: {os.path.basename(img_l_path)} / {os.path.basename(img_r_path)}")
            continue

        if img_l.shape[:2] != img_r.shape[:2]:
            print(f" - Tamanhos diferentes no par (ignorando): {os.path.basename(img_l_path)}")
            continue

        if img_shape is None:
            img_shape = (img_l.shape[1], img_l.shape[0])
        elif img_shape != (img_l.shape[1], img_l.shape[0]):
            print(f" - Tamanho diferente do primeiro par (ignorando): {os.path.basename(img_l_path)}")
            continue

        corners = detectar_cantos_estereo(img_l, img_r, rows, cols, criteria)
        if corners is not None:
            corners_l2, corners_r2 = corners
            objpoints.append(objp)
            imgpoints_l.append(corners_l2)
            imgpoints_r.append(corners_r2)
            kept_pairs.append((img_l_path, img_r_path))
            detected += 1
            print(f" + Tabuleiro detectado em: {os.path.basename(img_l_path)}")
        else:
            print(f" - Falha na deteccao em: {os.path.basename(img_l_path)}")
            bad_pairs.append((img_l_path, img_r_path))

        if processed % 25 == 0 or processed == len(valid_pairs):
            elapsed = time.perf_counter() - t0_det
            avg = elapsed / max(processed, 1)
            remaining = len(valid_pairs) - processed
            eta_s = remaining * avg
            print(
                f"Progresso: {processed}/{len(valid_pairs)} pares | "
                f"Detectados: {detected} | "
                f"Media: {avg:.3f}s/par | ETA deteccao: {eta_s / 60.0:.1f} min"
            )

    if not objpoints:
        raise RuntimeError(
            "Nenhum tabuleiro detectado. Verifique rows/cols e qualidade das imagens."
        )

    t_det = time.perf_counter() - t0_det
    print(f"Deteccao concluida: {detected} pares validos em {t_det / 60.0:.1f} min")
    print("Calibrando cameras... (isso pode demorar)")

    t0_cal = time.perf_counter()

    t0 = time.perf_counter()
    rms_l, mtx_l, dist_l, rvecs_l, tvecs_l = cv2.calibrateCamera(objpoints, imgpoints_l, img_shape, None, None)
    t_l = time.perf_counter() - t0
    err_l = calcular_erros_reprojecao(objpoints, imgpoints_l, rvecs_l, tvecs_l, mtx_l, dist_l)

    t0 = time.perf_counter()
    rms_r, mtx_r, dist_r, rvecs_r, tvecs_r = cv2.calibrateCamera(objpoints, imgpoints_r, img_shape, None, None)
    t_r = time.perf_counter() - t0
    err_r = calcular_erros_reprojecao(objpoints, imgpoints_r, rvecs_r, tvecs_r, mtx_r, dist_r)

    print(f"RMS Esquerda (cv2.calibrateCamera): {rms_l:.4f}")
    print(f"RMS Direita  (cv2.calibrateCamera): {rms_r:.4f}")
    print(f"Tempo intrinsecas: esq={t_l:.2f}s | dir={t_r:.2f}s")

    if salvar_pares_ruins_path:
        indices_ruins = np.argsort(err_r)[::-1][:top_n_piores]
        with open(salvar_pares_ruins_path, "w", encoding="utf-8") as f:
            print("\n--- Piores Imagens (DIREITA) ---")
            for idx in indices_ruins:
                nome_arq = os.path.basename(kept_pairs[idx][1])
                print(f"  Erro: {err_r[idx]:.4f} px | Arquivo: {nome_arq}")
                f.write(f"{kept_pairs[idx][0]}\n{kept_pairs[idx][1]}\n")

            if bad_pairs:
                print("\n--- Pares sem tabuleiro detectado ---")
                for l_path, r_path in bad_pairs:
                    print(f"  Sem deteccao: {os.path.basename(l_path)} / {os.path.basename(r_path)}")
                    f.write(f"{l_path}\n{r_path}\n")

        print(f"Lista salva em '{salvar_pares_ruins_path}'.")

    flags = cv2.CALIB_FIX_INTRINSIC
    t0 = time.perf_counter()
    ret_s, _, _, _, _, R, T, E, F = cv2.stereoCalibrate(
        objpoints,
        imgpoints_l,
        imgpoints_r,
        mtx_l,
        dist_l,
        mtx_r,
        dist_r,
        img_shape,
        criteria=criteria,
        flags=flags,
    )
    t_s = time.perf_counter() - t0

    print(f"Erro de reprojecao RMS: {ret_s:.4f}")
    print(f"Translacao (baseline estimado): {np.linalg.norm(T):.4f} {unidade_baseline}")
    print(f"Tempo estereo (cv2.stereoCalibrate): {t_s:.2f}s")

    t0 = time.perf_counter()
    if rectify_alpha is None:
        R1, R2, P1, P2, Q, roi1, roi2 = cv2.stereoRectify(mtx_l, dist_l, mtx_r, dist_r, img_shape, R, T)
    else:
        R1, R2, P1, P2, Q, roi1, roi2 = cv2.stereoRectify(
            mtx_l,
            dist_l,
            mtx_r,
            dist_r,
            img_shape,
            R,
            T,
            alpha=rectify_alpha,
        )
    t_rect = time.perf_counter() - t0
    print(f"Tempo retificacao (cv2.stereoRectify): {t_rect:.3f}s")

    np.savez(
        output_file,
        mtx_l=mtx_l,
        dist_l=dist_l,
        mtx_r=mtx_r,
        dist_r=dist_r,
        R=R,
        T=T,
        R1=R1,
        R2=R2,
        P1=P1,
        P2=P2,
        Q=Q,
    )

    t_cal = time.perf_counter() - t0_cal
    print(f"Dados salvos em '{output_file}'")
    print(f"Tempo total (calibracao+retificacao+save): {t_cal:.1f}s")

    return {
        "rms_stereo": float(ret_s),
        "rms_left": float(rms_l),
        "rms_right": float(rms_r),
        "detected_pairs": int(len(objpoints)),
        "total_pairs": int(len(valid_pairs)),
        "bad_pairs": int(len(bad_pairs)),
    }

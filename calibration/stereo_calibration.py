"""
Calibracao stereo robusta a partir de pares L/R de imagens de tabuleiro.

Modo de uso (programatico):
    from calibration.stereo_calibration import calibrar_stereo_robusta

    resultado = calibrar_stereo_robusta(
        dir_fotos="calibration/data/pares",
        rows=9,
        cols=6,
        square_size=5.0,
        output_file="calibration/npz_files/dados_calibracao.npz",
    )

Observacoes:
    - O nome dos arquivos deve permitir inferir pares L/R (ex.: *_L.jpg e *_R.jpg).
    - rows/cols representam cantos internos do tabuleiro.

Modo de uso (console):
    python3 calibration/stereo_calibration.py --dir-fotos calibration/data/pares --out calibration/npz_files/dados_calibracao.npz
"""

import glob
import os
import time
import argparse
from datetime import datetime

import cv2
import numpy as np

try:
    from .chessboard import construir_pontos_objeto, detectar_cantos_estereo
except ImportError:
    # Permite execucao direta: python3 calibration/stereo_calibration.py
    from chessboard import construir_pontos_objeto, detectar_cantos_estereo


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
    # Formato novo: dir_fotos/esquerda/*.png e dir_fotos/direita/*.png
    # (gerado por sync/audio_sync/sync_sbs_audio.py no modo frames_calib).
    dir_esq = os.path.join(dir_fotos, "esquerda")
    dir_dir = os.path.join(dir_fotos, "direita")

    if os.path.isdir(dir_esq) and os.path.isdir(dir_dir):
        padroes = ["*.png", "*.PNG", "*.jpg", "*.JPG"]
        imgs_esq = []
        imgs_dir = []
        for padrao in padroes:
            imgs_esq.extend(glob.glob(os.path.join(dir_esq, padrao)))
            imgs_dir.extend(glob.glob(os.path.join(dir_dir, padrao)))

        imgs_esq = sorted(imgs_esq)
        imgs_dir = sorted(imgs_dir)

        if not imgs_esq or not imgs_dir:
            return []

        # Chave de pareamento: parte antes de "_t" (ex.: frame_000123).
        mapa_dir = {}
        for img_r_path in imgs_dir:
            stem_r = os.path.splitext(os.path.basename(img_r_path))[0]
            chave_r = stem_r.split("_t", 1)[0]
            mapa_dir[chave_r] = img_r_path

        valid_pairs = []
        for img_l_path in imgs_esq:
            stem_l = os.path.splitext(os.path.basename(img_l_path))[0]
            chave_l = stem_l.split("_t", 1)[0]
            img_r_path = mapa_dir.get(chave_l)
            if img_r_path:
                valid_pairs.append((img_l_path, img_r_path))

        return valid_pairs

    # Formato legado: pares L/R no mesmo diretorio.
    # Busca imagens com marcador de esquerda no nome para inferir o par direito.
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


def _gerar_nome_npz_automatico(prefixo="dados_calibracao"):
    """Gera nome de arquivo .npz com sufixo de data/hora."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefixo}_{timestamp}.npz"


def calibrar_stereo_robusta(
    dir_fotos,
    rows=9,
    cols=6,
    square_size=5.0,
    output_file=None,
    output_dir=None,
    max_pairs=100,
    salvar_pares_ruins_path=None,
    top_n_piores=5,
    unidade_baseline="cm",
    rectify_alpha=None,
):
    """Calibra intrinsecas/extrinsecas stereo e salva matrizes de retificacao em .npz."""
    if output_file and output_dir:
        raise RuntimeError("Use apenas um entre output_file e output_dir.")

    if not output_file:
        nome_automatico = _gerar_nome_npz_automatico()
        output_file = os.path.join(output_dir, nome_automatico) if output_dir else nome_automatico

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
            "Nenhum par valido encontrado. Padroes aceitos: "
            "(1) Subpastas esquerda/ e direita/ com nomes equivalentes (ex.: frame_000001_t*.png), "
            "ou (2) pares L/R no mesmo diretorio: *_L.jpg/*_R.jpg, *_L.png/*_R.png, "
            "L_*.jpg/R_*.jpg, xxx-L.jpg/xxx-R.jpg"
        )

    print(f"Encontrados {len(valid_pairs)} pares de imagens validos para calibracao.")

    if max_pairs is not None and len(valid_pairs) > max_pairs:
        # Amostra uniforme para reduzir custo sem concentrar apenas no inicio/fim.
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


    # Intrinsecas camera esquerda.
    t0 = time.perf_counter()
    rms_l, mtx_l, dist_l, rvecs_l, tvecs_l = cv2.calibrateCamera(objpoints, imgpoints_l, img_shape, None, None)
    t_l = time.perf_counter() - t0
    err_l = calcular_erros_reprojecao(objpoints, imgpoints_l, rvecs_l, tvecs_l, mtx_l, dist_l)

    # Intrinsecas camera direita.
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
    # Estereo com intrinsecas fixas: estima apenas relacao entre cameras (R/T).
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

    # Gera transformacoes de retificacao para alinhar epipolares horizontalmente.
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

    out_dir = os.path.dirname(output_file)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calibracao stereo robusta com pares L/R de tabuleiro.")
    parser.add_argument("--dir-fotos", required=True, help="Diretorio com pares L/R")
    parser.add_argument("--rows", type=int, default=9, help="Numero de cantos internos verticais")
    parser.add_argument("--cols", type=int, default=6, help="Numero de cantos internos horizontais")
    parser.add_argument("--square-size", type=float, default=5.0, help="Tamanho do quadrado do tabuleiro")
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--out", help="Arquivo .npz de saida (nome manual)")
    output_group.add_argument("--out-dir", help="Pasta de saida; o nome .npz sera gerado automaticamente com data/hora")
    parser.add_argument("--max-pairs", type=int, default=100, help="Limite de pares usados na calibracao")
    parser.add_argument("--salvar-pares-ruins", help="Arquivo texto para salvar piores pares e pares sem deteccao")
    parser.add_argument("--top-n-piores", type=int, default=5, help="Quantidade de pares com maior erro a registrar")
    parser.add_argument("--unidade-baseline", default="cm", help="Unidade textual exibida para baseline")
    parser.add_argument("--rectify-alpha", type=float, help="Alpha da retificacao (0=crop maximo, 1=preserva FOV)")
    args = parser.parse_args()

    try:
        resultado = calibrar_stereo_robusta(
            dir_fotos=args.dir_fotos,
            rows=args.rows,
            cols=args.cols,
            square_size=args.square_size,
            output_file=args.out,
            output_dir=args.out_dir,
            max_pairs=args.max_pairs,
            salvar_pares_ruins_path=args.salvar_pares_ruins,
            top_n_piores=args.top_n_piores,
            unidade_baseline=args.unidade_baseline,
            rectify_alpha=args.rectify_alpha,
        )
    except RuntimeError as exc:
        raise SystemExit(f"Erro: {exc}")

    print("Resumo:")
    print(f"  RMS stereo: {resultado['rms_stereo']:.4f}")
    print(f"  RMS esquerda: {resultado['rms_left']:.4f}")
    print(f"  RMS direita: {resultado['rms_right']:.4f}")
    print(f"  Pares usados: {resultado['detected_pairs']}/{resultado['total_pairs']}")
    print(f"  Pares sem deteccao: {resultado['bad_pairs']}")

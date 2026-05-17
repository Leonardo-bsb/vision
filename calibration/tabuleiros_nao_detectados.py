"""
Imprime os pares de imagens em que nenhum tabuleiro valido foi detectado.

Modo de uso:
    python3 calibration/tabuleiros_nao_detectados.py --dir-fotos calibration/data/pares

Opcoes:
    --dir-fotos   Diretorio com os pares (subpastas esquerda/ e direita/ ou pares L/R).
    --rows        Linhas internas do tabuleiro (padrao: 9).
    --cols        Colunas internas do tabuleiro (padrao: 6).
    --saida       Arquivo de texto para salvar a lista de pares (opcional).
"""

import argparse
import os

import cv2

try:
    from .chessboard import construir_pontos_objeto, detectar_cantos_estereo
    from .stereo_calibration import _listar_pares_validos
except ImportError:
    from chessboard import construir_pontos_objeto, detectar_cantos_estereo
    from stereo_calibration import _listar_pares_validos


def listar_nao_detectados(dir_fotos, rows=9, cols=6):
    """Retorna lista de pares (l, r) onde a deteccao do tabuleiro falhou."""
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-4)

    pares = _listar_pares_validos(dir_fotos)
    if not pares:
        print("Nenhum par de imagens encontrado em:", dir_fotos)
        return []

    print(f"{len(pares)} pares encontrados. Verificando deteccao de tabuleiro...\n")

    nao_detectados = []
    for i, (img_l, img_r) in enumerate(pares, 1):
        frame_l = cv2.imread(img_l)
        frame_r = cv2.imread(img_r)

        prefixo = f"[{i:>{len(str(len(pares)))}}/{len(pares)}]"

        if frame_l is None or frame_r is None:
            print(f"{prefixo} ERRO LEITURA  E: {os.path.basename(img_l)} / D: {os.path.basename(img_r)}")
            nao_detectados.append((img_l, img_r))
            continue

        cantos = detectar_cantos_estereo(frame_l, frame_r, rows, cols, criteria)
        if cantos is None:
            print(f"{prefixo} NAO DETECTADO E: {os.path.basename(img_l)} / D: {os.path.basename(img_r)}")
            nao_detectados.append((img_l, img_r))

    return nao_detectados


def main():
    parser = argparse.ArgumentParser(
        description="Lista pares em que o tabuleiro nao foi detectado."
    )
    parser.add_argument("--dir-fotos", required=True, help="Diretorio com os pares de imagens.")
    parser.add_argument("--rows", type=int, default=9, help="Linhas internas do tabuleiro.")
    parser.add_argument("--cols", type=int, default=6, help="Colunas internas do tabuleiro.")
    parser.add_argument("--saida", default=None, help="Arquivo de saida para salvar a lista de pares.")
    args = parser.parse_args()

    nao_detectados = listar_nao_detectados(args.dir_fotos, args.rows, args.cols)

    total = nao_detectados.__len__()
    if total == 0:
        print("Tabuleiro detectado com sucesso em todos os pares.")
        return

    print(f"\n{'='*60}")
    print(f"Pares SEM tabuleiro detectado: {total}")
    print(f"{'='*60}")
    for i, (img_l, img_r) in enumerate(nao_detectados, 1):
        print(f"  [{i:>3}] E: {os.path.basename(img_l)}")
        print(f"        D: {os.path.basename(img_r)}")

    if args.saida:
        with open(args.saida, "w", encoding="utf-8") as f:
            for img_l, img_r in nao_detectados:
                f.write(f"{img_l}\n{img_r}\n")
        print(f"\nLista salva em '{args.saida}'.")


if __name__ == "__main__":
    main()

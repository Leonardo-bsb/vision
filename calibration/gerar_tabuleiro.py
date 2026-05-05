import argparse

import cv2
import numpy as np


def gerar_tabuleiro_para_impressao(
    rows=6,
    cols=6,
    lado_quadrado_mm=40,
    dpi=300,
    arquivo_saida="tabuleiro_print.png",
):
    """Gera uma imagem de alta resolucao para impressao do tabuleiro."""
    px_por_mm = dpi / 25.4
    square_size_px = int(lado_quadrado_mm * px_por_mm)

    squares_y = rows + 1
    squares_x = cols + 1
    margin_px = square_size_px

    height = squares_y * square_size_px + 2 * margin_px
    width = squares_x * square_size_px + 2 * margin_px

    img = np.ones((height, width), dtype=np.uint8) * 255

    print("Gerando tabuleiro...")
    print(f" - Padrao (Cantos Internos): {rows}x{cols}")
    print(f" - Quadrados Reais: {squares_y}x{squares_x}")
    print(f" - Tamanho do Quadrado: {lado_quadrado_mm}mm ({square_size_px}px a {dpi} DPI)")
    print(f" - Dimensao Total da Imagem: {width}x{height} pixels")

    start_x = margin_px
    start_y = margin_px

    for y in range(squares_y):
        for x in range(squares_x):
            if (x + y) % 2 != 0:
                pt1 = (start_x + x * square_size_px, start_y + y * square_size_px)
                pt2 = (pt1[0] + square_size_px, pt1[1] + square_size_px)
                cv2.rectangle(img, pt1, pt2, 0, -1)

    cv2.imwrite(arquivo_saida, img)
    print(f"Salvo em: {arquivo_saida}")

    try:
        from PIL import Image

        pil_img = Image.fromarray(img)
        arquivo_pdf = arquivo_saida.rsplit(".", 1)[0] + ".pdf"
        pil_img.save(arquivo_pdf, "PDF", resolution=dpi)
        print(f"Salvo tambem em PDF: {arquivo_pdf}")
    except ImportError:
        print("AVISO: Instale 'Pillow' para gerar a versao em PDF.")

    print("Leve este arquivo para impressao em tamanho real (100%).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera tabuleiro de calibracao para impressao.")
    parser.add_argument("--rows", type=int, default=9, help="Numero de cantos internos verticais")
    parser.add_argument("--cols", type=int, default=6, help="Numero de cantos internos horizontais")
    parser.add_argument("--lado-mm", type=float, default=50.0, help="Tamanho do lado do quadrado em mm")
    parser.add_argument("--dpi", type=int, default=300, help="Resolucao da imagem")
    parser.add_argument("--out", default="tabuleiro_medio_9x6_50mm.png", help="Arquivo de saida")
    args = parser.parse_args()

    gerar_tabuleiro_para_impressao(
        rows=args.rows,
        cols=args.cols,
        lado_quadrado_mm=args.lado_mm,
        dpi=args.dpi,
        arquivo_saida=args.out,
    )
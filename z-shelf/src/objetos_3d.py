import cv2
import numpy as np
import argparse
import os
import sys

"""
OBJETIVO: Retificar imagens estéreo usando calibração prévia e calcular mapa de disparidade.
Entrada: Duas imagens (esquerda/direita) e um arquivo .npz de calibração.
Saída: Imagens retificadas lado a lado (opcionalmente), mapa de disparidade.
       Gera 'rectified_check.png' (alinhamento) e 'disparity.png' (profundidade).

USO:
    python3 src/objetos_3d.py \
        --left data/img_esq.png \
        --right data/img_dir.png \
        --calib data/calib.npz \
        --out verificacao.png

    # Você também pode passar um diretório em --out; o script salvará um arquivo
    # padrão dentro dele:
    python3 src/objetos_3d.py \
        --left data/img_esq.png \
        --right data/img_dir.png \
        --calib data/calib.npz \
        --out data/output/

    Opcional:
        --swap  # Use se você suspeitar que Esquerda/Direita foram invertidas
        --tune-y N # Ajuste fino vertical na imagem da Direita.
                   Use (+) se a Direita estiver mais ALTA que a Esquerda (empurra p/ baixo).
                   Use (-) se a Direita estiver mais BAIXA que a Esquerda (puxa p/ cima).
        --wls-lambda FLOAT # Parâmetro Lambda do WLS (padrão 8000.0). Valores maiores = mais liso.
        --wls-sigma FLOAT  # Parâmetro Sigma do WLS (padrão 1.5). Sensibilidade a bordas.
        --scale FLOAT      # Fator de escala (0.1 a 1.0) para reduzir resolução e acelerar (padrão 1.0).

    Melhorias recentes:
    - Filtro WLS: Adicionado pós-processamento que suaviza a disparidade baseada na textura da imagem colorida.
    - Argumentos Extras: Adicionei --wls-lambda e --wls-sigma para você poder brincar com a suavização (valores maiores = mais liso).

    O script gera um arquivo PNG (lossless) mostrando as duas imagens alinhadas
    com linhas verdes horizontais. Se a calibração estiver boa, as linhas
    passarão pelos mesmos pontos em ambas as imagens.
    
    Também gera um arquivo '_disparity.png' mostrando a profundidade:
    - Cores quentes (amarelo/vermelho): Perto
    - Cores frias (azul/roxo): Longe
    
    E um arquivo '_segmented.png' com os objetos detectados e numerados.

    DICA DE QUALIDADE:
    Instale 'opencv-contrib-python' para ativar o filtro WLS automaticamente.
    Isso remove ruídos e melhora muito a definição das bordas.
"""

def load_stereo_coefficients(path):
    """Carrega os coeficientes de calibração do arquivo .npz."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Arquivo de calibração não encontrado: {path}")
    
    data = np.load(path)
    # Verifica se as chaves essenciais para retificação existem
    required_keys = ['mtx_l', 'dist_l', 'R1', 'P1', 'mtx_r', 'dist_r', 'R2', 'P2']
    if not all(key in data for key in required_keys):
        raise ValueError("O arquivo .npz não contém todas as chaves necessárias (R1, P1, R2, P2, etc).")
        
    return data

def rectify_stereo_images(img_l, img_r, calib_data):
    """
    Aplica a retificação estéreo nas imagens esquerda e direita
    usando os mapas de distorção e projeção pré-calculados.
    """
    # Obtém dimensões da imagem atual
    h, w = img_l.shape[:2]

    # Extrai Matrizes da Esquerda
    mtx_l = calib_data['mtx_l']
    dist_l = calib_data['dist_l']
    R1 = calib_data['R1']
    P1 = calib_data['P1']

    # Extrai Matrizes da Direita
    mtx_r = calib_data['mtx_r']
    dist_r = calib_data['dist_r']
    R2 = calib_data['R2']
    P2 = calib_data['P2']

    # Gera mapas de retificação
    # initUndistortRectifyMap calcula a transformação de cada pixel para corrigir distorção e alinhar epipolares
    map1_l, map2_l = cv2.initUndistortRectifyMap(mtx_l, dist_l, R1, P1, (w, h), cv2.CV_16SC2)
    map1_r, map2_r = cv2.initUndistortRectifyMap(mtx_r, dist_r, R2, P2, (w, h), cv2.CV_16SC2)

    # Aplica o remapeamento (interpolação linear é rápida e suave)
    rect_l = cv2.remap(img_l, map1_l, map2_l, cv2.INTER_LINEAR) #Interpolação bilinear
    rect_r = cv2.remap(img_r, map1_r, map2_r, cv2.INTER_LINEAR)

    return rect_l, rect_r

def compute_disparity(img_l, img_r, num_disp=160, block_size=5, use_wls=True, wls_lambda=8000.0, wls_sigma=1.5):
    """Calcula o mapa de disparidade usando SGBM e opcionalmente filtro WLS."""
    # Garante que num_disp é múltiplo de 16
    if num_disp % 16 != 0:
        num_disp = ((num_disp // 16) + 1) * 16
    
    gray_l = cv2.cvtColor(img_l, cv2.COLOR_BGR2GRAY)
    gray_r = cv2.cvtColor(img_r, cv2.COLOR_BGR2GRAY)
    
    # Configuração do SGBM (Left Matcher)
    left_matcher = cv2.StereoSGBM_create(
        minDisparity=0,
        numDisparities=num_disp,
        blockSize=block_size,
        P1=8 * 3 * block_size**2,
        P2=32 * 3 * block_size**2,
        disp12MaxDiff=1,
        uniquenessRatio=10,
        speckleWindowSize=100,
        speckleRange=32,
        mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY
    )
    
    # Tenta usar o filtro WLS se solicitado (requer opencv-contrib-python)
    if use_wls:
        try:
            # Verifica se o módulo ximgproc está disponível
            right_matcher = cv2.ximgproc.createRightMatcher(left_matcher)
            
            print("Calculando disparidade (Esq+Dir) para filtro WLS...")
            disp_l = left_matcher.compute(gray_l, gray_r)
            disp_r = right_matcher.compute(gray_r, gray_l)
            
            wls_filter = cv2.ximgproc.createDisparityWLSFilter(matcher_left=left_matcher)
            wls_filter.setLambda(wls_lambda)
            wls_filter.setSigmaColor(wls_sigma)
            
            print(f"Aplicando filtro WLS (Lambda={wls_lambda}, Sigma={wls_sigma})...")
            filtered_disp = wls_filter.filter(disp_l, img_l, disparity_map_right=disp_r)
            
            # Retorna normalizado (WLS retorna int16 fix point, igual SGBM)
            return filtered_disp.astype(np.float32) / 16.0
            
        except AttributeError:
            print("\n[AVISO] 'cv2.ximgproc' não encontrado. O filtro WLS foi desativado.")
            print("DICA: Instale 'pip install opencv-contrib-python' para melhorar drasticamente a qualidade.\n")
        except Exception as e:
            print(f"[AVISO] Erro ao aplicar WLS: {e}. Usando SGBM padrão.")

    # Fallback: SGBM padrão sem filtro
    return left_matcher.compute(gray_l, gray_r).astype(np.float32) / 16.0

def segment_and_visualize(disparity, img, min_area=1000):
    """
    Segmenta objetos baseando-se no mapa de disparidade.
    Objetos mais próximos têm maior disparidade (são mais claros no mapa).
    """
    # 1. Normalização robusta (ignorando valores <= 0)
    valid_pixels = disparity > 0
    if not np.any(valid_pixels):
        print("[AVISO] Mapa de disparidade vazio ou inválido. Pulei a segmentação.")
        return img.copy()

    disp_norm = np.zeros_like(disparity, dtype=np.uint8)
    disp_norm[valid_pixels] = cv2.normalize(disparity[valid_pixels], None, 0, 255, cv2.NORM_MINMAX)

    # 2. Limiarização (Threshold)
    # Otsu ajuda a encontrar o limiar automático entre fundo (longe) e objetos (perto)
    _, mask = cv2.threshold(disp_norm, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 3. Limpeza Morfológica (remove ruídos e fecha buracos)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    # 4. Encontrar Contornos
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 5. Desenhar Resultados
    vis_img = img.copy()
    obj_count = 0
    
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > min_area:
            obj_count += 1
            x, y, w, h = cv2.boundingRect(cnt)
            cv2.rectangle(vis_img, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(vis_img, f"#{obj_count}", (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    print(f"Segmentação: {obj_count} objetos detectados (Area min: {min_area})")
    return vis_img

def main():
    parser = argparse.ArgumentParser(description="Retificação Estéreo: Passo 1 para Objetos 3D")
    parser.add_argument("--left", required=True, help="Caminho da imagem Esquerda")
    parser.add_argument("--right", required=True, help="Caminho da imagem Direita")
    parser.add_argument("--calib", required=True, help="Caminho do arquivo .npz de calibração") #Matrizes intrínsecas, de distorção, rotação e projeção
    parser.add_argument("--out", default="rectified_check.png", help="Arquivo de saída para verificação")
    parser.add_argument("--swap", action="store_true", help="Troca os canais Esquerda e Direita")
    parser.add_argument("--tune-y", type=int, default=0, help="Ajuste vertical na Dir: (+) desce, (-) sobe")
    parser.add_argument("--num-disp", type=int, default=160, help="Faixa de busca de profundidade (múltiplo de 16)")
    parser.add_argument("--block-size", type=int, default=5, help="Tamanho do bloco de comparação (ímpar, ex: 3, 5, 7)")
    parser.add_argument("--no-wls", action="store_true", help="Desativa o filtro WLS (mais rápido, menos qualidade)")
    parser.add_argument("--wls-lambda", type=float, default=8000.0, help="Parâmetro Lambda do WLS (suavização)")
    parser.add_argument("--wls-sigma", type=float, default=1.5, help="Parâmetro Sigma do WLS (sensibilidade a bordas)")
    parser.add_argument("--scale", type=float, default=1.0, help="Fator de escala para processamento (ex: 0.5)")
    parser.add_argument("--min-area", type=int, default=2000, help="Área mínima (pixels) para considerar um objeto")
    
    args = parser.parse_args()

    # 1. Carregar Imagens
    if not os.path.exists(args.left) or not os.path.exists(args.right):
        print("Erro: Imagens de entrada não encontradas.")
        sys.exit(1)

    img_l = cv2.imread(args.left)
    img_r = cv2.imread(args.right)
    
    if args.swap:
        print("--> Trocando canais: Esquerda <-> Direita")
        img_l, img_r = img_r, img_l

    # 2. Carregar Calibração
    try:
        print(f"Carregando calibração: {args.calib}")
        calib_data = load_stereo_coefficients(args.calib)
    except Exception as e:
        print(f"Erro crítico ao carregar calibração: {e}")
        sys.exit(1)
        
    # Verificação de Resolução e Redimensionamento Automático
    h_img, w_img = img_l.shape[:2]
    mtx_l = calib_data['mtx_l']
    
    # Estima a resolução da calibração baseada no centro óptico (cx, cy)
    # cx ~ width/2, cy ~ height/2
    w_calib = int(mtx_l[0, 2] * 2)
    h_calib = int(mtx_l[1, 2] * 2)
    
    # Se a diferença for significativa (>5%), redimensiona a entrada
    if abs(w_img - w_calib) > (w_calib * 0.05):
        print(f"\n[INFO] Resolução diferente detectada (Img: {w_img}x{h_img} vs Calib: ~{w_calib}x{h_calib})")
        print(f"       -> Redimensionando imagens para a resolução de calibração...")
        img_l = cv2.resize(img_l, (w_calib, h_calib), interpolation=cv2.INTER_AREA)
        img_r = cv2.resize(img_r, (w_calib, h_calib), interpolation=cv2.INTER_AREA)

    # 3. Retificar
    print("Aplicando retificação geométrica...")
    rect_l, rect_r = rectify_stereo_images(img_l, img_r, calib_data)

    # 3.1 Ajuste Fino Vertical (Manual)
    if args.tune_y != 0:
        print(f"Aplicando ajuste fino vertical de {args.tune_y} pixels na imagem da Direita...")
        M = np.float32([[1, 0, 0], [0, 1, args.tune_y]])
        rect_r = cv2.warpAffine(rect_r, M, (rect_r.shape[1], rect_r.shape[0]))

    # 3.2 Downscale opcional para performance (após retificação)
    if args.scale != 1.0 and args.scale > 0:
        h, w = rect_l.shape[:2]
        new_size = (int(w * args.scale), int(h * args.scale))
        print(f"Redimensionando para cálculo de disparidade ({args.scale}x): {new_size}")
        rect_l = cv2.resize(rect_l, new_size, interpolation=cv2.INTER_AREA)
        rect_r = cv2.resize(rect_r, new_size, interpolation=cv2.INTER_AREA)

    # 4. Calcular Disparidade (Profundidade)
    print("Calculando mapa de disparidade (SGBM)...")
    disp = compute_disparity(
        rect_l, rect_r, num_disp=args.num_disp, block_size=args.block_size,
        use_wls=not args.no_wls, wls_lambda=args.wls_lambda, wls_sigma=args.wls_sigma
    )
    
    # Normaliza para visualização (Color Map)
    # Ignora valores <= 0 para a visualização
    disp_vis = np.maximum(disp, 0)
    disp_vis = cv2.normalize(disp_vis, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    disp_color = cv2.applyColorMap(disp_vis, cv2.COLORMAP_PLASMA)

    # 5. Segmentar Objetos
    print("Segmentando objetos...")
    segmented_img = segment_and_visualize(disp, rect_l, min_area=args.min_area)

    # 6. Visualizar Resultado (Side-by-Side com linhas)
    # Mostra as imagens lado a lado para fácil comparação
    vis = np.hstack((rect_l, rect_r))
    for y in range(0, vis.shape[0], 50):
        cv2.line(vis, (0, y), (vis.shape[1], y), (0, 255, 0), 1)

    # Tratamento robusto do caminho de saída
    out_path = args.out
    
    # Se terminar com barra, trata como diretório (cria se não existir)
    if out_path.endswith(os.sep) or out_path.endswith("/"):
        if not os.path.exists(out_path):
            os.makedirs(out_path)
        out_path = os.path.join(out_path, "rectified_check.png")
    
    # Se for um diretório existente (mesmo sem barra)
    elif os.path.isdir(out_path):
        out_path = os.path.join(out_path, "rectified_check.png")
        
    # Se não tiver extensão conhecida, adiciona .png
    elif not any(out_path.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg']):
        out_path += ".png"

    # Garante que a pasta pai existe
    parent_dir = os.path.dirname(out_path)
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir)

    # Salva imagem de verificação (Alinhamento)
    success = cv2.imwrite(out_path, vis)
    abs_path = os.path.abspath(out_path)
    
    # Salva imagem de disparidade (Profundidade)
    disp_out_path = out_path.replace(".png", "_disparity.png")
    cv2.imwrite(disp_out_path, disp_color)

    # Salva imagem segmentada
    seg_out_path = out_path.replace(".png", "_segmented.png")
    cv2.imwrite(seg_out_path, segmented_img)
    
    if success:
        print(f"Sucesso! Arquivos gerados:\n  1. Alinhamento: {abs_path}\n  2. Profundidade: {disp_out_path}\n  3. Segmentação: {seg_out_path}")
    else:
        print(f"ERRO: Falha ao salvar a imagem (cv2.imwrite retornou False).")
        print(f"      Verifique permissões ou espaço em disco.")
        print(f"      Tentou salvar em: {abs_path}")

if __name__ == "__main__":
    main()

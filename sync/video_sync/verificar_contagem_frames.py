# =============================================================================
# VERIFICADOR DE CONTAGEM DE FRAMES (DRIFT CHECK)
# =============================================================================
# Este script percorre os vídeos em intervalos de tempo (ex: a cada 5 min)
# e mostra o número do frame correspondente naquele timestamp.
#
# Útil para verificar se as câmeras estão gravando com a mesma taxa de quadros
# ou se há desvio (drift) na contagem de frames ao longo do tempo.
#
# Uso:
#    python3 sync/video_sync/verificar_contagem_frames.py LEFT.MP4 RIGHT.MP4 --intervalo 5
# =============================================================================

import cv2
import argparse
import os
import sys

def verificar_frames(video_esq, video_dir, intervalo_minutos=5):
    if not os.path.exists(video_esq) or not os.path.exists(video_dir):
        print("Erro: Um ou mais arquivos de vídeo não foram encontrados.")
        return

    cap_esq = cv2.VideoCapture(video_esq)
    cap_dir = cv2.VideoCapture(video_dir)

    if not cap_esq.isOpened() or not cap_dir.isOpened():
        print("Erro ao abrir os vídeos com OpenCV.")
        return

    # Obtém FPS e Duração Total (em frames e segundos)
    fps_esq = cap_esq.get(cv2.CAP_PROP_FPS)
    fps_dir = cap_dir.get(cv2.CAP_PROP_FPS)
    
    total_frames_esq = int(cap_esq.get(cv2.CAP_PROP_FRAME_COUNT))
    total_frames_dir = int(cap_dir.get(cv2.CAP_PROP_FRAME_COUNT))
    
    duracao_esq = total_frames_esq / fps_esq if fps_esq > 0 else 0
    duracao_dir = total_frames_dir / fps_dir if fps_dir > 0 else 0
    
    min_duracao = min(duracao_esq, duracao_dir)

    print(f"{'='*80}")
    print(f"ANÁLISE DE FRAMES POR INTERVALO (A cada {intervalo_minutos} min)")
    print(f"{'='*80}")
    print(f"ESQUERDA: {video_esq}")
    print(f"  FPS: {fps_esq:.4f} | Total Frames: {total_frames_esq} | Duração: {duracao_esq/60:.2f} min")
    print(f"DIREITA:  {video_dir}")
    print(f"  FPS: {fps_dir:.4f} | Total Frames: {total_frames_dir} | Duração: {duracao_dir/60:.2f} min")
    print(f"{'-'*80}")
    print(f"{'Tempo (min)':<12} | {'Frame Esq':<12} | {'Frame Dir':<12} | {'Diferença':<10}")
    print(f"{'-'*80}")

    # Loop pelos intervalos
    tempo_atual_min = 0
    while (tempo_atual_min * 60) <= min_duracao:
        tempo_ms = tempo_atual_min * 60 * 1000
        
        # Posiciona o vídeo no tempo desejado
        cap_esq.set(cv2.CAP_PROP_POS_MSEC, tempo_ms)
        cap_dir.set(cv2.CAP_PROP_POS_MSEC, tempo_ms)
        
        # Lê o índice do frame atual
        frame_esq = int(cap_esq.get(cv2.CAP_PROP_POS_FRAMES))
        frame_dir = int(cap_dir.get(cv2.CAP_PROP_POS_FRAMES))
        
        diff = frame_esq - frame_dir
        
        print(f"{tempo_atual_min:<12.1f} | {frame_esq:<12} | {frame_dir:<12} | {diff:<10}")
        
        tempo_atual_min += intervalo_minutos

    print(f"{'-'*80}")
    print("Nota: A contagem baseada em 'seek' (pular tempo) pode ter pequenas imprecisões")
    print("devido aos keyframes do codec de vídeo (GOP), mas serve para ver a tendência.")
    print(f"{'='*80}")

    cap_esq.release()
    cap_dir.release()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verifica a contagem de frames em intervalos de tempo.")
    parser.add_argument("esq", help="Caminho do vídeo da Esquerda")
    parser.add_argument("dir", help="Caminho do vídeo da Direita")
    parser.add_argument("--intervalo", type=float, default=5.0, help="Intervalo em minutos para checagem (padrão: 5).")
    
    args = parser.parse_args()
    
    verificar_frames(args.esq, args.dir, args.intervalo)
import argparse
import subprocess
import cv2
import os
import sys


def resolve_output_file(video_path, output_file, default_name):
    base_dir = os.path.dirname(os.path.abspath(video_path))
    if output_file:
        if os.path.isabs(output_file) or os.path.dirname(output_file):
            return output_file
        return os.path.join(base_dir, output_file)
    return os.path.join(base_dir, default_name)


def ensure_parent_dir(path):
    parent_dir = os.path.dirname(path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

def gerar_clip_teste(video_esq, video_dir, ajuste, drift_ms, duracao, output_file):
    if not os.path.exists(video_esq) or not os.path.exists(video_dir):
        print("Erro: Vídeos não encontrados.")
        return

    # 1. Calcular Fator de Drift e Duração
    cap = cv2.VideoCapture(video_esq)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_esq = frame_count / fps
    cap.release()

    # Cálculo do Fator (Mesma lógica do ajuste fino)
    duration_dir_estimada = duration_esq - (drift_ms / 1000.0)
    drift_factor = 1.0
    if duration_dir_estimada > 0:
        drift_factor = duration_esq / duration_dir_estimada

    # 2. Calcular Ponto de Início (Meio do Vídeo)
    middle_time = duration_esq / 2
    start_time_rel = max(0, middle_time - (duracao / 2))
    
    print(f"{'='*60}")
    print(f"GERAR CLIP DE TESTE (MEIO DO JOGO)")
    print(f"{'='*60}")
    print(f"Duração Total: {duration_esq:.2f}s")
    print(f"Início do Clip: {start_time_rel:.2f}s (Meio do jogo)")
    print(f"Ajuste Inicial: {ajuste}s")
    print(f"Drift Total:    {drift_ms}ms")
    print(f"Fator Correção: {drift_factor:.10f}")
    print(f"{'-'*60}")

    # 3. Calcular Cortes (Trims)
    # Base do ajuste inicial
    base_trim_esq = 0.0
    base_trim_dir = 0.0
    if ajuste > 0: base_trim_dir = ajuste
    else: base_trim_esq = abs(ajuste)
    
    # Adiciona o tempo de início do clip
    # Para a esquerda, é direto.
    final_trim_esq = base_trim_esq + start_time_rel
    
    # Para a direita, precisamos compensar o drift acumulado até a metade
    # Se o vídeo da direita corre em velocidade diferente, o tempo 't' nele é t / factor
    final_trim_dir = base_trim_dir + (start_time_rel / drift_factor)

    output_file = resolve_output_file(video_esq, output_file, "clip_teste_meio.mp4")
    ensure_parent_dir(output_file)
    
    # Filtro: Corta no ponto certo, reseta o relógio (PTS), aplica o fator de velocidade na direita
    filter_complex = (
        f"[0:v]trim=start={final_trim_esq},setpts=PTS-STARTPTS[l];"
        f"[1:v]trim=start={final_trim_dir},setpts=(PTS-STARTPTS)*{drift_factor:.10f}[r];"
        f"[l][r]hstack=inputs=2[v]"
    )
    
    cmd = [
        "ffmpeg", "-y", "-v", "warning",
        "-i", video_esq,
        "-i", video_dir,
        "-filter_complex", filter_complex,
        "-t", str(duracao),  # Duração do clip
        "-map", "[v]",
        "-map", "0:a",       # Usa áudio da esquerda
        "-c:v", "libx264", "-crf", "23", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k",
        output_file
    ]
    
    print(f"Gerando clip de {duracao}s em: {output_file}")
    subprocess.run(cmd)
    print("Concluído.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--esq", required=True)
    parser.add_argument("--dir", required=True)
    parser.add_argument("--ajuste", type=float, required=True)
    parser.add_argument("--drift", type=float, required=True)
    parser.add_argument("--duracao", type=int, default=60, help="Duração do clip em segundos")
    parser.add_argument("--out", help="Arquivo de saída. Se omitido, salva ao lado do vídeo esquerdo.")
    args = parser.parse_args()
    
    gerar_clip_teste(args.esq, args.dir, args.ajuste, args.drift, args.duracao, args.out)
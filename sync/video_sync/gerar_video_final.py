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

def gerar_video_final(video_esq, video_dir, ajuste, drift_ms, output_file):
    if not os.path.exists(video_esq) or not os.path.exists(video_dir):
        print("Erro: Vídeos não encontrados.")
        return

    # 1. Calcular Fator de Drift
    cap = cv2.VideoCapture(video_esq)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_esq = frame_count / fps
    cap.release()

    duration_dir_estimada = duration_esq - (drift_ms / 1000.0)
    
    drift_factor = 1.0
    if duration_dir_estimada > 0:
        drift_factor = duration_esq / duration_dir_estimada

    print(f"{'='*60}")
    print(f"GERAR VÍDEO FINAL SINCRONIZADO")
    print(f"{'='*60}")
    print(f"Ajuste (Offset): {ajuste} s")
    print(f"Drift Total:     {drift_ms} ms")
    print(f"Fator Correção:  {drift_factor:.10f}")
    print(f"{'-'*60}")

    # 2. Calcular Cortes Iniciais (Offset)
    trim_esq = 0.0
    trim_dir = 0.0
    
    if ajuste > 0:
        trim_dir = ajuste
    elif ajuste < 0:
        trim_esq = abs(ajuste)

    # 3. Montar Comando FFmpeg
    output_file = resolve_output_file(video_esq, output_file, "video_final_sync.mp4")
    ensure_parent_dir(output_file)
    
    # Aplica o corte inicial e depois corrige a velocidade (PTS) da direita
    filter_complex = (
        f"[0:v]trim=start={trim_esq},setpts=PTS-STARTPTS[l];"
        f"[1:v]trim=start={trim_dir},setpts=(PTS-STARTPTS)*{drift_factor:.10f}[r];"
        f"[l][r]hstack=inputs=2[v]"
    )
    
    cmd = [
        "ffmpeg", "-y",
        "-i", video_esq,
        "-i", video_dir,
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "0:a", # Usa áudio da esquerda
        "-c:v", "libx264", "-crf", "23", "-preset", "medium",
        "-c:a", "aac", "-b:a", "192k",
        output_file
    ]
    
    print("Executando FFmpeg (isso pode demorar)...")
    print(" ".join(cmd))
    subprocess.run(cmd)
    print(f"Vídeo salvo em: {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--esq", required=True)
    parser.add_argument("--dir", required=True)
    parser.add_argument("--ajuste", type=float, required=True)
    parser.add_argument("--drift", type=float, required=True)
    parser.add_argument("--out", help="Arquivo de saída. Se omitido, salva ao lado do vídeo esquerdo.")
    args = parser.parse_args()
    
    gerar_video_final(args.esq, args.dir, args.ajuste, args.drift, args.out)
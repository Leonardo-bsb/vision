import cv2
import numpy as np
import os
import subprocess
import sys
import argparse


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

def encontrar_frame_flash(video_path, max_frames=2400):
    """
    Lê os primeiros frames do vídeo e retorna o índice do frame com maior brilho médio (flash).
    """
    if not os.path.exists(video_path):
        print(f"Erro: Arquivo não encontrado: {video_path}")
        sys.exit(1)

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    brightness_values = []
    frame_idx = 0
    
    print(f"Analisando brilho em {os.path.basename(video_path)}...")
    
    while frame_idx < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
            
        # Converte para escala de cinza e calcula a média de brilho dos pixels
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        avg_brightness = np.mean(gray)
        brightness_values.append(avg_brightness)
        frame_idx += 1
        
    cap.release()

    if not brightness_values:
        return 0, fps, 0

    # 1. Detecção de Pico Relativo (Spike)
    # Em vez de pegar o brilho máximo absoluto (que pode ser o sol),
    # pegamos o frame que mais se destaca em relação aos vizinhos (flash).
    b_vals = np.array(brightness_values)
    scores = np.zeros_like(b_vals)
    window = 15  # Janela para calcular o "piso" de luz ambiente

    for i in range(len(b_vals)):
        s = max(0, i - window)
        e = min(len(b_vals), i + window + 1)
        local_min = np.min(b_vals[s:e])
        # O score é o quanto este frame é mais brilhante que o ambiente imediato
        scores[i] = b_vals[i] - local_min

    max_score = np.max(scores)
    max_idx = np.argmax(scores)

    # 2. Ajuste Fino: Olhar 3 frames antes e depois para calcular o "centro de massa" do flash
    start = max(0, max_idx - 3)
    end = min(len(scores), max_idx + 4)
    
    # Usamos os SCORES para o peso, pois eles representam apenas a luz do flash (sem a luz do dia)
    window_scores = scores[start:end]
    window_idxs = range(start, end)
    
    weighted_sum = sum(i * s for i, s in zip(window_idxs, window_scores))
    total_weight = sum(window_scores)
    
    final_frame = max_idx
    if total_weight > 0:
        center_of_mass = weighted_sum / total_weight
        final_frame = int(round(center_of_mass))
        
    # Feedback visual no terminal
    print(f"   [Detalhe] Frame Pico: {max_idx} | Score Flash: {max_score:.2f}")
    if final_frame != max_idx:
        print(f"   [Ajuste] Centro do flash ajustado para frame {final_frame}")

    return final_frame, fps, max_score

def gerar_comando_ffmpeg(video_esq, video_dir, frame_esq, frame_dir, output_file):
    """
    Gera o comando FFmpeg para cortar e juntar os vídeos lado a lado.
    """
    # O filtro trim corta o vídeo a partir do frame do flash.
    # setpts=PTS-STARTPTS reseta o tempo para começar do zero.
    # hstack coloca os vídeos lado a lado.
    filter_complex = (
        f"[0:v]trim=start_frame={frame_esq},setpts=PTS-STARTPTS[l];"
        f"[1:v]trim=start_frame={frame_dir},setpts=PTS-STARTPTS[r];"
        f"[l][r]hstack"
    )
    
    # Comando completo
    cmd = [
        "ffmpeg", "-y",
        "-i", video_esq,
        "-i", video_dir,
        "-filter_complex", filter_complex,
        "-c:v", "libx264", "-crf", "23", "-preset", "fast",
        output_file
    ]
    
    return cmd, output_file

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sincroniza videos stereo pelo flash.")
    parser.add_argument("esq", help="Caminho do vídeo da Esquerda")
    parser.add_argument("dir", help="Caminho do vídeo da Direita")
    parser.add_argument("--ajuste_esq", type=int, default=0, help="Adiciona/Remove frames do corte da Esquerda")
    parser.add_argument("--ajuste_dir", type=int, default=0, help="Adiciona/Remove frames do corte da Direita")
    parser.add_argument("--out", help="Arquivo de saída. Se omitido, salva ao lado do vídeo esquerdo.")
    args = parser.parse_args()

    # Caminhos dos arquivos
    p_esq = args.esq
    p_dir = args.dir
    
    # 1. Encontrar o flash (analisa os primeiros ~5-10 segundos)
    f_esq, fps, _ = encontrar_frame_flash(p_esq, max_frames=2400)
    f_dir, _, _ = encontrar_frame_flash(p_dir, max_frames=2400)
    
    print(f"\n--- SINCRONIA DETECTADA (AUTO) ---")
    print(f"Esquerda: Flash no frame {f_esq}")
    print(f"Direita:  Flash no frame {f_dir}")
    
    # Aplicar ajustes manuais (se fornecidos)
    f_esq = max(0, f_esq + args.ajuste_esq)
    f_dir = max(0, f_dir + args.ajuste_dir)

    if args.ajuste_esq != 0 or args.ajuste_dir != 0:
        print(f"\n--- APLICANDO AJUSTES MANUAIS ---")
        print(f"Esquerda: {f_esq} (Manual: {args.ajuste_esq})")
        print(f"Direita:  {f_dir} (Manual: {args.ajuste_dir})")

    # 2. Executar FFmpeg
    output = resolve_output_file(p_esq, args.out, "video_3d_sincronizado_SBS.mp4")
    ensure_parent_dir(output)
    cmd, output = gerar_comando_ffmpeg(p_esq, p_dir, f_esq, f_dir, output)
    print(f"\nGerando vídeo sincronizado: {output} ...")
    subprocess.run(cmd)
    print("Concluído!")
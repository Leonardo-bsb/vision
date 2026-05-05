# =============================================================================
# ANALISADOR DE DRIFT DE TIMESTAMPS
# =============================================================================
# Este script compara os carimbos de tempo (timestamps) absolutos de dois vídeos
# em intervalos fixos de frames (ex: a cada 24.000 frames).
#
# Objetivo: Verificar se, ao avançar a mesma quantidade de frames em ambos,
# o tempo "relógio" (Wall Clock) diverge, indicando Clock Drift ou diferença de FPS.
#
# Uso:
#    python3 src/sync/analisar_drift_timestamps.py --esq <video_esq> --dir <video_dir> [opções]
#
# Opções:
#    --ajuste X        : Ajuste manual em segundos.
#    --drift X         : Drift em ms a cada intervalo.
#    --step X          : Intervalo de frames (padrão: 2400).
#    --time_esq X      : Timestamp manual ESQ (YYYY-MM-DDTHH:MM:SS).
#    --time_dir X      : Timestamp manual DIR (YYYY-MM-DDTHH:MM:SS).
# =============================================================================

import cv2


def resolve_output_dir(video_path, output_dir, default_dir_name):
    if output_dir:
        if os.path.isabs(output_dir) or os.path.dirname(output_dir):
            return output_dir
        return os.path.join(os.path.dirname(os.path.abspath(video_path)), output_dir)
    return os.path.join(os.path.dirname(os.path.abspath(video_path)), default_dir_name)
import argparse
import os
import sys
import subprocess
import json
from datetime import datetime, timedelta

def ler_data_criacao(video_path):
    """
    Lê a data de criação dos metadados de um arquivo de vídeo usando ffprobe.

#    python3 sync/video_sync/analisar_drift_timestamps.py --esq <video_esq> --dir <video_dir> [opções]
        video_path (str): Caminho para o arquivo de vídeo.

    Returns:
        datetime: Objeto datetime com a data de criação, ou None se falhar.
    """
    if not os.path.exists(video_path):
        print(f"Erro: Arquivo '{video_path}' não encontrado.")
        sys.exit(1)

    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_entries", "format_tags",
        video_path
    ]
    
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(res.stdout)
        tags = data.get("format", {}).get("tags", {})
        
        # Busca case-insensitive por creation_time
        c_time = None
        for k, v in tags.items():
            if k.lower() == "creation_time":
                c_time = v
                break
        
        if c_time:
            c_time = c_time.replace("Z", "")
            if "." in c_time:
                return datetime.strptime(c_time, "%Y-%m-%dT%H:%M:%S.%f")
            else:
                return datetime.strptime(c_time, "%Y-%m-%dT%H:%M:%S")
        
        print(f"Aviso: 'creation_time' não encontrado em: {video_path}")
        print(f"Tags disponíveis: {list(tags.keys())}")
        return None
    except Exception as e:
        print(f"Erro ao ler metadados de {video_path}: {e}")
        return None

def analisar_timestamps(video_esq, video_dir, step_frames=2400, ajuste=0.0, drift_ms=0.0, manual_ts_esq=None, manual_ts_dir=None):
    """
    Analisa o drift temporal entre dois vídeos comparando timestamps e frames.

    Esta função percorre os dois vídeos em intervalos definidos (step_frames),
    calcula o tempo absoluto esperado e extrai frames para verificação visual.
    Permite aplicar ajustes manuais de sincronia inicial e correção de drift (clock drift).

    Args:
        video_esq (str): Caminho do vídeo da esquerda.
        video_dir (str): Caminho do vídeo da direita.
        step_frames (int): Intervalo de frames para avançar a cada iteração.
        ajuste (float): Ajuste inicial em segundos para sincronizar o começo.
        drift_ms (float): Correção de drift em milissegundos a ser aplicada a cada intervalo.
    """
    # 1. Obter Data de Criação (Absoluta)
    t0_esq = None
    if manual_ts_esq:
        try:
            t0_esq = datetime.strptime(manual_ts_esq, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            print("Erro: Formato inválido para --time_esq. Use YYYY-MM-DDTHH:MM:SS")
            return
    else:
        t0_esq = ler_data_criacao(video_esq)

    t0_dir = None
    if manual_ts_dir:
        try:
            t0_dir = datetime.strptime(manual_ts_dir, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            print("Erro: Formato inválido para --time_dir. Use YYYY-MM-DDTHH:MM:SS")
            return
    else:
        t0_dir = ler_data_criacao(video_dir)

    # Se não encontrou data de criação, usa uma data fictícia para permitir análise relativa
    if not t0_esq:
        print(f"Aviso: Timestamp não encontrado para ESQ. Usando data base (00:00:00) para análise relativa.")
        t0_esq = datetime(2000, 1, 1)
    
    if not t0_dir:
        print(f"Aviso: Timestamp não encontrado para DIR. Usando data base (00:00:00) para análise relativa.")
        t0_dir = datetime(2000, 1, 1)

    # 2. Abrir Vídeos para pegar FPS e Duração
    cap_esq = cv2.VideoCapture(video_esq)
    cap_dir = cv2.VideoCapture(video_dir)

    fps_esq = cap_esq.get(cv2.CAP_PROP_FPS)
    fps_dir = cap_dir.get(cv2.CAP_PROP_FPS)
    
    frames_total_esq = int(cap_esq.get(cv2.CAP_PROP_FRAME_COUNT))
    frames_total_dir = int(cap_dir.get(cv2.CAP_PROP_FRAME_COUNT))

    duracao_esq_sec = frames_total_esq / fps_esq
    duracao_dir_sec = frames_total_dir / fps_dir
    output_debug = resolve_output_dir(video_esq, output_debug_dir, "frames_debug")
    # 3. Calcular Ponto de Partida com Ajuste Manual
    # Lógica idêntica ao sincronizar_metadata.py
    diff_sync = (t0_esq - t0_dir).total_seconds() + ajuste
    
    trim_esq = 0.0
    trim_dir = 0.0
    
    if diff_sync > 0:
        trim_dir = diff_sync
    else:
        trim_esq = abs(diff_sync)

    # Começamos a análise 10 segundos após o ponto de sincronia calculado
    start_delay = 10.0
    
    frame_atual_esq = float((trim_esq + start_delay) * fps_esq)
    frame_atual_dir = float((trim_dir + start_delay) * fps_dir)

    print(f"{'='*100}")
    print(f"ANÁLISE DE TIMESTAMPS (Intervalo: {step_frames} frames)")
    print(f"Ajuste Manual Aplicado: {ajuste:+.4f}s")
    if drift_ms != 0.0:
        print(f"Drift Aplicado: {drift_ms:+.4f} ms a cada {step_frames} frames")
    print(f"{'='*100}")
    print(f"ESQ: {t0_esq} | FPS: {fps_esq:.4f}")
    print(f"DIR: {t0_dir} | FPS: {fps_dir:.4f}")
    print(f"{'-'*100}")
    print(f"{'Frame (E/D)':<15} | {'Tempo Absoluto ESQ':<26} | {'Tempo Absoluto DIR':<26} | {'Diff (s)':<10}")
    print(f"{'-'*100}")

    # Cria diretório para salvar frames de debug
    output_debug = "data/output/frames_debug"
    os.makedirs(output_debug, exist_ok=True)
    print(f"Salvando frames de debug em: {output_debug}")

    # 5. Loop de Análise
    first_iter = True
    while True:
        # Verifica se passou do fim
        if frame_atual_esq >= frames_total_esq or frame_atual_dir >= frames_total_dir:
            break

        # Pega o timestamp relativo do frame (MSEC)
        # Nota: Usamos cálculo direto (frame/fps) pois CAP_PROP_POS_MSEC costuma ser derivado disso
        # Se houver drift real de hardware, ele aparecerá se o FPS do arquivo for diferente
        # ou se compararmos com um relógio externo. Comparando metadados, veremos a "verdade do arquivo".
        
        ts_esq = t0_esq + timedelta(seconds=frame_atual_esq / fps_esq)
        ts_dir = t0_dir + timedelta(seconds=frame_atual_dir / fps_dir)
        
        diff = (ts_esq - ts_dir).total_seconds()

        # Calcula próximos frames para saber se é a última iteração
        next_esq = frame_atual_esq + step_frames
        next_dir = frame_atual_dir + step_frames + (drift_ms / 1000.0 * fps_dir)
        is_last = (next_esq >= frames_total_esq or next_dir >= frames_total_dir)

        # Só lê e salva frames se for o primeiro ou o último
        if first_iter or is_last:
    parser.add_argument("--out-dir", help="Pasta para salvar os frames de debug. Se omitido, salva ao lado do vídeo esquerdo.")
            # Salvar frames para conferência visual
    analisar_timestamps(args.esq, args.dir, step_frames=args.step, ajuste=args.ajuste, drift_ms=args.drift, manual_ts_esq=args.time_esq, manual_ts_dir=args.time_dir, output_debug_dir=args.out_dir)
            cap_esq.set(cv2.CAP_PROP_POS_MSEC, (frame_atual_esq / fps_esq) * 1000.0)
            ret_esq, img_esq = cap_esq.read()
            
            cap_dir.set(cv2.CAP_PROP_POS_MSEC, (frame_atual_dir / fps_dir) * 1000.0)
            ret_dir, img_dir = cap_dir.read()

            if ret_esq and ret_dir:
                # Garante mesmo tamanho para concatenar (caso haja pequena diferença de resolução)
                if img_esq.shape != img_dir.shape:
                    img_dir = cv2.resize(img_dir, (img_esq.shape[1], img_esq.shape[0]))
                
                combined = cv2.hconcat([img_esq, img_dir])
                fname_combined = f"frame_E{int(frame_atual_esq):08d}_D{int(frame_atual_dir):08d}_combined.jpg"
                cv2.imwrite(os.path.join(output_debug, fname_combined), combined)

        print(f"{int(frame_atual_esq):<7}/{int(frame_atual_dir):<7} | {str(ts_esq):<26} | {str(ts_dir):<26} | {diff:+.4f}")

        frame_atual_esq = next_esq
        frame_atual_dir = next_dir
        first_iter = False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analisa o drift de timestamps entre dois vídeos, comparando o tempo absoluto em intervalos de frames.", allow_abbrev=False)
    parser.add_argument("--esq", required=True, help="Caminho do vídeo da Esquerda.")
    parser.add_argument("--dir", required=True, help="Caminho do vídeo da Direita.")
    parser.add_argument("--ajuste", type=float, default=0.0, help="Ajuste manual em segundos.")
    parser.add_argument("--drift", type=float, default=0.0, help="Drift em milisegundos a cada intervalo (step).")
    parser.add_argument("--step", type=int, default=2400, help="Intervalo de frames para análise (padrão: 2400).")
    parser.add_argument("--time_esq", help="Timestamp manual ESQ (YYYY-MM-DDTHH:MM:SS) para ignorar metadados.")
    parser.add_argument("--time_dir", help="Timestamp manual DIR (YYYY-MM-DDTHH:MM:SS) para ignorar metadados.")
    args = parser.parse_args()
    analisar_timestamps(args.esq, args.dir, step_frames=args.step, ajuste=args.ajuste, drift_ms=args.drift, manual_ts_esq=args.time_esq, manual_ts_dir=args.time_dir)
# =============================================================================
# COMO USAR ESTE SCRIPT:
# =============================================================================
# Sincroniza dois vídeos lado a lado baseando-se no relógio interno (metadata).
#
# Uso básico:
#    python3 sync/video_sync/sincronizar_metadata.py videos/left.mp4 videos/right.mp4
#
# Ajuste Manual (--ajuste):
#    Se a sincronia automática não ficar perfeita, use a opção --ajuste com o valor em SEGUNDOS.
#
#    Regra de Sinais para o Ajuste:
#    1. Se o vídeo da ESQUERDA está "adiantado" (mostra um tempo maior no cronômetro):
#       Use valor POSITIVO (ex: --ajuste 0.33)
#
#    2. Se o vídeo da DIREITA está "adiantado" (mostra um tempo maior):
#       Use valor NEGATIVO (ex: --ajuste -0.33)
# =============================================================================

import argparse
import subprocess
import json
import os
import sys
from datetime import datetime


def resolve_output_file(video_path, output_name, default_name):
    base_dir = os.path.dirname(os.path.abspath(video_path))
    if output_name:
        if os.path.isabs(output_name) or os.path.dirname(output_name):
            return output_name
        return os.path.join(base_dir, output_name)
    return os.path.join(base_dir, default_name)


def ensure_parent_dir(path):
    parent_dir = os.path.dirname(path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

def ler_data_criacao(video_path):
    """
    Lê a data de criação dos metadados de um arquivo de vídeo usando ffprobe.

    Args:
        video_path (str): Caminho para o arquivo de vídeo.

    Returns:
        datetime: Objeto datetime com a data de criação, ou None se falhar.
    """
    if not os.path.exists(video_path):
        print(f"Erro: Arquivo '{video_path}' não encontrado.")
        sys.exit(1)

    # ffprobe para ler metadados
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_entries", "format_tags=creation_time",
        video_path
    ]
    
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(res.stdout)
        tags = data.get("format", {}).get("tags", {})
        c_time = tags.get("creation_time")
        
        if c_time:
            # Formato típico: 2024-02-07T20:36:28.000000Z ou 2024-02-07T20:36:28Z
            c_time = c_time.replace("Z", "")
            
            # Tenta com microsegundos
            if "." in c_time:
                return datetime.strptime(c_time, "%Y-%m-%dT%H:%M:%S.%f")
            else:
                # Tenta sem microsegundos
                return datetime.strptime(c_time, "%Y-%m-%dT%H:%M:%S")
        return None
    except Exception as e:
        print(f"Erro ao ler metadados de {video_path}: {e}")
        return None

def gerar_video_sincronizado(video_esq, video_dir, ajuste=0.0, output_name=None, duracao=60):
    """
    Gera um vídeo sincronizado lado a lado (3D/Stereo) baseando-se nos metadados de tempo.

    Calcula a diferença de tempo entre o início das gravações e corta (trim) o vídeo
    que começou mais cedo para alinhar o tempo zero.

    Args:
        video_esq (str): Caminho do vídeo da esquerda.
        video_dir (str): Caminho do vídeo da direita.
        ajuste (float): Ajuste manual em segundos para somar/subtrair da diferença calculada.
        output_name (str, optional): Nome do arquivo de saída. Se None, gera automático.
    """
    t_esq = ler_data_criacao(video_esq)
    t_dir = ler_data_criacao(video_dir)
    
    if t_esq is None or t_dir is None:
        print("ERRO: Não foi possível obter a data de criação de um dos vídeos.")
        print("Verifique se os arquivos são originais da câmera.")
        return

    print(f"--- SINCRONIA POR METADADOS (Relógio Interno) ---")
    print(f"Esquerda: {t_esq}")
    print(f"Direita:  {t_dir}")
    
    # Diferença em segundos (float)
    diff = (t_esq - t_dir).total_seconds()
    
    print(f"Diferença detectada: {diff:.4f} segundos")
    
    if ajuste != 0:
        print(f"Aplicando ajuste manual: {ajuste:+.4f} segundos")
        diff += ajuste
        print(f"Diferença final considerada: {diff:.4f} segundos")
    
    trim_esq = 0
    trim_dir = 0
    
    # Lógica de corte:
    # Se diff > 0: Esquerda (t_esq) é maior (mais tarde) que Direita (t_dir).
    # Significa que a Direita começou a gravar ANTES.
    # Ex: Esq=10:05, Dir=10:00. Diff=5.
    # A Direita tem 5 segundos a mais no início. Cortamos 5s da Direita.
    if diff > 0:
        print(f"Ajuste: Cortando {diff:.4f}s do início da DIREITA.")
        trim_dir = diff
    elif diff < 0:
        diff = abs(diff)
        print(f"Ajuste: Cortando {diff:.4f}s do início da ESQUERDA.")
        trim_esq = diff
    else:
        print("Vídeos iniciados exatamente no mesmo segundo.")

    output_file = resolve_output_file(video_esq, output_name, "video_3d_sync_metadata.mp4")
    ensure_parent_dir(output_file)
    
    # Filtro complexo para cortar e juntar lado a lado
    filter_complex = (
        f"[0:v]trim=start={trim_esq},setpts=PTS-STARTPTS[l];"
        f"[1:v]trim=start={trim_dir},setpts=PTS-STARTPTS[r];"
        f"[l][r]hstack=inputs=2:shortest=1"
    )
    
    cmd = [
        "ffmpeg", "-y",
        "-i", video_esq,
        "-i", video_dir,
        "-filter_complex", filter_complex,
        "-t", str(duracao),
        "-c:v", "libx264", "-crf", "23", "-preset", "fast",
        output_file
    ]
    
    print(f"Gerando vídeo: {output_file} ...")
    subprocess.run(cmd)
    print("Concluído!")
    print(f"Output: {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sincroniza vídeos usando o relógio interno (metadata).")
    parser.add_argument("esq", help="Caminho do vídeo da Esquerda")
    parser.add_argument("dir", help="Caminho do vídeo da Direita")
    parser.add_argument("--ajuste", type=float, default=0.0, help="Ajuste manual em segundos (some ou subtraia da diferença detectada).")
    parser.add_argument("--t", type=int, default=60, help="Tempo de duração do vídeo em segundos")
    parser.add_argument("-o", "--output", help="Arquivo de saída. Se omitido, salva ao lado do vídeo esquerdo.")
    args = parser.parse_args()
    
    gerar_video_sincronizado(args.esq, args.dir, args.ajuste, args.output, args.t)
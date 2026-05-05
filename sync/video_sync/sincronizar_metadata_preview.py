# =============================================================================
# SCRIPT DE PREVIEW (TESTE RÁPIDO DE SINCRONIA)
# =============================================================================
# Baseado em sincronizar_metadata.py, mas gera apenas 1 minuto de vídeo.
# Ideal para testar rapidamente o valor do --ajuste antes de processar tudo.
#
# Uso:
#    python3 sync/video_sync/sincronizar_metadata_preview.py LEFT.MP4 RIGHT.MP4 --ajuste 0.67 -t 20
#
# Opções:
#    --ajuste X        : Ajuste manual em segundos (padrão: 0.0)
#    -t X, --duracao X : Duração do preview em segundos (padrão: 60)
#    -o X, --output X  : Nome do arquivo de saída (opcional)
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
    """Lê a data de criação dos metadados e retorna um objeto datetime."""
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
            c_time = c_time.replace("Z", "")
            if "." in c_time:
                return datetime.strptime(c_time, "%Y-%m-%dT%H:%M:%S.%f")
            else:
                return datetime.strptime(c_time, "%Y-%m-%dT%H:%M:%S")
        return None
    except Exception as e:
        print(f"Erro ao ler metadados de {video_path}: {e}")
        return None

def gerar_preview_sincronizado(video_esq, video_dir, ajuste=0.0, duracao=60, output_name=None):
    t_esq = ler_data_criacao(video_esq)
    t_dir = ler_data_criacao(video_dir)
    
    if t_esq is None or t_dir is None:
        print("ERRO: Não foi possível obter a data de criação de um dos vídeos.")
        return

    print(f"--- PREVIEW DE SINCRONIA (Limitado a {duracao}s) ---")
    print(f"Esquerda: {t_esq}")
    print(f"Direita:  {t_dir}")
    
    diff = (t_esq - t_dir).total_seconds()
    print(f"Diferença detectada: {diff:.4f} segundos")
    
    if ajuste != 0:
        print(f"Aplicando ajuste manual: {ajuste:+.4f} segundos")
        diff += ajuste
        print(f"Diferença final considerada: {diff:.4f} segundos")
    
    trim_esq = 0
    trim_dir = 0
    
    if diff > 0:
        print(f"Ajuste: Cortando {diff:.4f}s do início da DIREITA.")
        trim_dir = diff
    elif diff < 0:
        diff = abs(diff)
        print(f"Ajuste: Cortando {diff:.4f}s do início da ESQUERDA.")
        trim_esq = diff
    else:
        print("Vídeos iniciados exatamente no mesmo segundo.")

    output_file = resolve_output_file(
        video_esq,
        output_name,
        f"video_3d_sync_preview_adj{ajuste:.3f}.mp4",
    )
    ensure_parent_dir(output_file)
    
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
        "-t", str(duracao),  # Limita a duração do output
        "-c:v", "libx264", "-crf", "23", "-preset", "fast",
        output_file
    ]
    
    print(f"Gerando PREVIEW: {output_file} ...")
    subprocess.run(cmd)
    print("Concluído!")
    print(f"Output: {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera um preview curto (1 min) da sincronização.")
    parser.add_argument("esq", help="Caminho do vídeo da Esquerda")
    parser.add_argument("dir", help="Caminho do vídeo da Direita")
    parser.add_argument("--ajuste", type=float, default=0.0, help="Ajuste manual em segundos.")
    parser.add_argument("-t", "--duracao", type=int, default=60, help="Duração do preview em segundos (padrão: 60).")
    parser.add_argument("-o", "--output", help="Arquivo de saída. Se omitido, salva ao lado do vídeo esquerdo.")
    args = parser.parse_args()
    
    gerar_preview_sincronizado(args.esq, args.dir, args.ajuste, args.duracao, args.output)
# =============================================================================
# ANALISADOR DE DRIFT DE ÁUDIO
# =============================================================================
# Este script analisa a correlação de áudio entre dois vídeos em intervalos
# regulares para detectar se há desvio (drift) temporal ao longo da gravação.
#
# Diferente do sincronizar_audio.py, este script não gera vídeo novo, apenas
# relata os dados para análise e gera um gráfico com os drifts x tempo.
#
# Uso:
#    python3 src/sync/analisar_drift_audio.py [video_esq] [video_dir] [--intervalo S] [--janela S]
#
# Exemplo:
#    python3 src/sync/analisar_drift_audio.py videos/LEFT.MP4 videos/RIGHT.MP4 --intervalo 60
# =============================================================================

import subprocess
import numpy as np
import os
import sys
import argparse
import cv2


def resolve_output_dir(video_path, output_dir, default_dir_name):
    if output_dir:
        if os.path.isabs(output_dir) or os.path.dirname(output_dir):
            return output_dir
        base_dir = os.path.dirname(os.path.abspath(video_path))
        return os.path.join(base_dir, output_dir)
    return os.path.join(os.path.dirname(os.path.abspath(video_path)), default_dir_name)

# Tenta importar scipy, instala se necessário
try:
    from scipy.io import wavfile
    from scipy.signal import correlate
except ImportError:
    print("Biblioteca 'scipy' não encontrada. Instalando...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "scipy"])
        from scipy.io import wavfile
        from scipy.signal import correlate
    except Exception as e:
        print(f"Erro ao instalar scipy: {e}")
        sys.exit(1)

HAS_PLOT = False
try:
    import matplotlib.pyplot as plt
    HAS_PLOT = True
except ImportError:
    print("Biblioteca 'matplotlib' não encontrada. Instalando...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "matplotlib"])
        import matplotlib.pyplot as plt
        HAS_PLOT = True
    except Exception as e:
        print(f"Erro ao instalar matplotlib: {e}. O gráfico não será gerado.")

def get_video_duration(video_path):
    """Obtém a duração do vídeo em segundos usando OpenCV."""
    if not os.path.exists(video_path):
        print(f"Erro: Arquivo não encontrado: {video_path}")
        sys.exit(1)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return 0
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    duration = frame_count / fps if fps > 0 else 0
    cap.release()
    return duration

def extrair_trecho_audio(video_path, audio_out, start_time, duration):
    """Extrai um trecho de áudio (mono, 16kHz) usando ffmpeg."""
    if os.path.exists(audio_out):
        os.remove(audio_out)
    
    # -ss antes do -i é "fast seek" (busca por keyframe). 
    # Para áudio, a precisão costuma ser suficiente e é muito mais rápido que decodificar tudo.
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", str(start_time),
        "-i", video_path,
        "-t", str(duration),
        "-ac", "1", "-ar", "16000",
        audio_out
    ]
    subprocess.run(cmd, check=True)

def calcular_delay_trecho(wav_esq, wav_dir):
    """Calcula o atraso entre dois arquivos WAV usando correlação cruzada."""
    try:
        rate_e, sig_e = wavfile.read(wav_esq)
        rate_d, sig_d = wavfile.read(wav_dir)
    except ValueError:
        return None

    if len(sig_e) == 0 or len(sig_d) == 0:
        return None

    # Normalização Z-Score (remove média e divide pelo desvio padrão)
    std_e = np.std(sig_e)
    std_d = np.std(sig_d)
    
    if std_e == 0 or std_d == 0:
        return 0.0 # Silêncio absoluto

    sig_e = (sig_e - np.mean(sig_e)) / std_e
    sig_d = (sig_d - np.mean(sig_d)) / std_d

    # Realça os transientes (batidas/estalos)
    sig_e = np.abs(np.diff(sig_e))
    sig_d = np.abs(np.diff(sig_d))
    
    sig_e = (sig_e - np.mean(sig_e)) / (np.std(sig_e) + 1e-10)
    sig_d = (sig_d - np.mean(sig_d)) / (np.std(sig_d) + 1e-10)

    # Correlação Cruzada via FFT
    correlation = correlate(sig_e, sig_d, mode='full', method='fft')
    lags = np.arange(-len(sig_d) + 1, len(sig_e))
    
    lag_idx = np.argmax(correlation)
    lag_samples = lags[lag_idx]
    
    return lag_samples / rate_e

def analisar_drift(video_esq, video_dir, intervalo, janela, output_dir=None):
    dur_esq = get_video_duration(video_esq)
    dur_dir = get_video_duration(video_dir)
    min_dur = min(dur_esq, dur_dir)
    
    print(f"{'='*80}")
    print(f"ANÁLISE DE DRIFT DE ÁUDIO")
    print(f"{'='*80}")
    print(f"Esq: {video_esq} ({dur_esq:.2f}s)")
    print(f"Dir: {video_dir} ({dur_dir:.2f}s)")
    print(f"Config: Intervalo={intervalo}s, Janela={janela}s")
    print(f"{'-'*80}")
    print(f"{'Tempo (s)':<12} | {'Atraso (s)':<15} | {'Drift (ms)':<15}")
    print(f"{'-'*80}")
    
    temp_wav_esq = "temp_drift_esq.wav"
    temp_wav_dir = "temp_drift_dir.wav"
    
    current_time = 0.0
    first_delay = None
    
    times = []
    drifts = []
    
    try:
        while current_time + janela < min_dur:
            try:
                extrair_trecho_audio(video_esq, temp_wav_esq, current_time, janela)
                extrair_trecho_audio(video_dir, temp_wav_dir, current_time, janela)
                
                delay = calcular_delay_trecho(temp_wav_esq, temp_wav_dir)
                
                if delay is not None:
                    if first_delay is None:
                        first_delay = delay
                    
                    # Drift é a variação do atraso em relação ao início
                    drift = (delay - first_delay) * 1000.0
                    print(f"{current_time:<12.1f} | {delay:<15.6f} | {drift:<15.4f}")
                    
                    times.append(current_time)
                    drifts.append(drift)
                else:
                    print(f"{current_time:<12.1f} | {'N/A':<15} | {'-':<15}")
                    
            except subprocess.CalledProcessError:
                print(f"{current_time:<12.1f} | {'Erro FFmpeg':<15} | {'-':<15}")
            except Exception as e:
                print(f"{current_time:<12.1f} | {str(e):<15} | {'-':<15}")
                
            current_time += intervalo
            
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuário.")
    finally:
        # Limpeza
        if os.path.exists(temp_wav_esq): os.remove(temp_wav_esq)
        if os.path.exists(temp_wav_dir): os.remove(temp_wav_dir)
        print(f"{'-'*80}")
        
        if len(times) > 0 and HAS_PLOT:
            try:
                output_dir = resolve_output_dir(video_esq, output_dir, "results")
                os.makedirs(output_dir, exist_ok=True)
                output_plot = os.path.join(output_dir, "drift_audio_plot.png")
                
                plt.figure(figsize=(10, 6))
                plt.plot(times, drifts, marker='o', linestyle='-', label='Drift Medido')
                
                if len(times) > 1:
                    z = np.polyfit(times, drifts, 1)
                    p = np.poly1d(z)
                    plt.plot(times, p(times), "r--", label=f'Tendência ({z[0]:.4f} ms/s)')
                
                plt.title(f"Drift de Áudio: {os.path.basename(video_esq)} vs {os.path.basename(video_dir)}")
                plt.xlabel("Tempo (s)")
                plt.ylabel("Drift (ms)")
                plt.grid(True)
                plt.legend()
                plt.tight_layout()
                plt.savefig(output_plot)
                print(f"Gráfico salvo em: {output_plot}")
            except Exception as e:
                print(f"Erro ao gerar gráfico: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analisa o drift de áudio entre dois vídeos ao longo do tempo.")
    parser.add_argument("esq", help="Caminho do vídeo da Esquerda")
    parser.add_argument("dir", help="Caminho do vídeo da Direita")
    parser.add_argument("--intervalo", type=float, default=60.0, help="Intervalo entre análises em segundos (padrão: 60)")
    parser.add_argument("--janela", type=float, default=10.0, help="Duração do trecho de áudio a analisar em cada passo (padrão: 10)")
    parser.add_argument("--out-dir", help="Pasta para salvar o gráfico de saída. Se omitido, salva ao lado do vídeo esquerdo.")
    
    args = parser.parse_args()
    
    analisar_drift(args.esq, args.dir, args.intervalo, args.janela, args.out_dir)
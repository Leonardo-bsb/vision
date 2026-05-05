# =============================================================================
# SCRIPT DE SINCRONIZAÇÃO POR ÁUDIO E RETIFICAÇÃO ESTÉREO
# =============================================================================
# Este script sincroniza dois vídeos (Esquerda e Direita) analisando a correlação
# entre suas faixas de áudio. Ele encontra o atraso temporal e gera um novo
# vídeo lado a lado (Side-by-Side) perfeitamente alinhado.
#
# Funcionalidades:
#    - Sincronia Temporal: Alinha o início dos vídeos pelo áudio (palma/claquete).
#    - Correção de Drift: Compensa diferenças de relógio entre câmeras em vídeos longos.
#    - Retificação Estéreo (Opcional): Se fornecido um arquivo .npz, corrige a distorção
#      da lente e alinha as linhas epipolares para visualização 3D perfeita.
#
# Uso:
#    python3 src/sync/audio_sync/sincronizar_audio.py [video_esq] [video_dir] [opções]
#
# Exemplos:
#    1. Sincronia Simples (Rápida, sem correção de lente):
#       python3 src/sync/audio_sync/sincronizar_audio.py data/input/videos/LEFT.MP4 data/input/videos/RIGHT.MP4
#
#    2. Sincronia + Retificação (Recomendado para 3D/VR):
#       python3 src/sync/audio_sync/sincronizar_audio.py data/input/videos/LEFT.MP4 data/input/videos/RIGHT.MP4 \
#         --calib data/calibration/nzd_files/dados_calibracao.npz
#
#    3. Com Drift Automático (Vídeos > 5min):
#       python3 src/sync/audio_sync/sincronizar_audio.py ... --auto-drift
#
#    4. Com Duração Limitada (ex: 60 segundos para teste):
#       python3 src/sync/audio_sync/sincronizar_audio.py ... -t 60
#
#    5. Alta Resolução (Intel QuickSync):
#       Para vídeos 2.7K ou 4K lado a lado (largura > 4096px), use HEVC:
#       python3 src/sync/audio_sync/sincronizar_audio.py ... --calib ... --encoder hevc_qsv
# =============================================================================

import subprocess
import numpy as np
import os
import sys
import argparse
import cv2
from datetime import datetime

# Tenta importar scipy, se não tiver, avisa ou tenta instalar
try:
    from scipy.io import wavfile
    from scipy.signal import correlate
except ImportError:
    print("Biblioteca 'scipy' não encontrada. Instalando...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "scipy"])
    from scipy.io import wavfile
    from scipy.signal import correlate

def match_color_stats(source, target):
    """
    Transfere a média e desvio padrão de cores da imagem 'target' para 'source'.
    Corrige diferenças de balanço de branco e exposição.
    """
    s_mean, s_std = cv2.meanStdDev(source)
    t_mean, t_std = cv2.meanStdDev(target)
    
    s_mean = s_mean.flatten()
    s_std = s_std.flatten()
    t_mean = t_mean.flatten()
    t_std = t_std.flatten()
    
    source = source.astype(np.float32)
    for i in range(3):
        scale = t_std[i] / (s_std[i] + 1e-6)
        source[:,:,i] = (source[:,:,i] - s_mean[i]) * scale + t_mean[i]
    
    return np.clip(source, 0, 255).astype(np.uint8)

def extrair_audio_temporario(video_path, audio_out, start_time=0, duracao=20):
    """Extrai um trecho de áudio do vídeo para um arquivo WAV leve (mono, 16kHz) para análise."""
    if os.path.exists(audio_out):
        os.remove(audio_out)
        
    # Comando FFmpeg:
    # -ss: Ponto de início (seek)
    # -t: Limita a duração (analisar o vídeo todo é lento e desnecessário)
    # -ac 1: Converte para Mono (1 canal)
    # -ar 16000: Taxa de amostragem 16kHz (suficiente para voz/batidas e rápido de processar)
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", str(start_time),
        "-i", video_path,
        "-t", str(duracao),
        "-ac", "1", "-ar", "16000",
        audio_out
    ]
    subprocess.run(cmd, check=True)

def calcular_atraso_audio(wav_esq, wav_dir):
    """
    Calcula o atraso (lag) entre dois áudios usando correlação cruzada.
    Retorna o tempo em segundos que o vídeo da Esquerda deve ser deslocado.

    Explicação do Cálculo:
    1. Leitura: Carrega os áudios (mono, 16kHz).
    2. Normalização (Z-Score): Subtrai a média e divide pelo desvio padrão.
       - Isso iguala a escala de volume e centraliza o "silêncio" em zero.
    3. Correlação Cruzada (FFT): Desliza um sinal sobre o outro para achar a semelhança.
       - method='fft' usa Transformada de Fourier para acelerar o cálculo (O(N log N)).
    4. Pico (Argmax): O ponto mais alto do gráfico de correlação é o "match" perfeito.
       - O índice desse pico diz quantas amostras (samples) de distância eles estão.
    5. Conversão: Amostras / Taxa de Amostragem = Segundos.
    """
    rate, sig_esq = wavfile.read(wav_esq)
    _, sig_dir = wavfile.read(wav_dir)
    
    # Normalização Z-Score: Remove a média e divide pelo desvio padrão.
    # Isso torna a comparação robusta a diferenças de volume entre as câmeras.
    sig_esq = (sig_esq - np.mean(sig_esq)) / (np.std(sig_esq) + 1e-10)
    sig_dir = (sig_dir - np.mean(sig_dir)) / (np.std(sig_dir) + 1e-10)
    
    # print("Correlacionando sinais de áudio...") # Comentado para não poluir no loop de drift
    # A correlação cruzada desliza um sinal sobre o outro para achar o ponto de maior semelhança.
    # Usar FFT (Transformada Rápida de Fourier) acelera drasticamente esse cálculo.
    correlation = correlate(sig_esq, sig_dir, mode='full', method='fft')
    lags = np.arange(-len(sig_dir) + 1, len(sig_esq))
    
    # O índice onde a correlação é máxima indica o melhor alinhamento
    lag_idx = np.argmax(correlation)
    lag_samples = lags[lag_idx]
    
    # Converte amostras para segundos
    tempo_atraso = lag_samples / rate
    return tempo_atraso

def calcular_drift_automatico(video_esq, video_dir, duracao_total):
    """Calcula a taxa de drift analisando amostras ao longo de todo o vídeo."""
    print(f"\n{'='*60}")
    print(f"CALCULANDO DRIFT AUTOMÁTICO (Amostragem)")
    print(f"{'='*60}")
    
    intervalo = 60.0  # Analisar a cada 60 segundos
    janela = 10.0     # Analisar trechos de 10 segundos
    
    times = []
    delays = []
    
    current_time = 0.0
    temp_esq = "temp_drift_calc_esq.wav"
    temp_dir = "temp_drift_calc_dir.wav"
    
    try:
        while current_time + janela < duracao_total:
            try:
                extrair_audio_temporario(video_esq, temp_esq, start_time=current_time, duracao=janela)
                extrair_audio_temporario(video_dir, temp_dir, start_time=current_time, duracao=janela)
                
                delay = calcular_atraso_audio(temp_esq, temp_dir)
                
                times.append(current_time)
                delays.append(delay)
                print(f"  T={current_time:6.1f}s | Delay={delay:8.5f}s")
            except Exception as e:
                print(f"  T={current_time:6.1f}s | Erro na leitura: {e}")
            
            current_time += intervalo
            
        if len(times) > 1:
            # Regressão Linear: Delay = slope * tempo + intercept
            z = np.polyfit(times, delays, 1)
            slope = z[0] # Variação do delay por segundo (s/s)
            total_drift_ms = (slope * duracao_total) * 1000.0
            print(f"{'-'*60}")
            print(f"Taxa de Drift: {slope*1000:.4f} ms/s")
            print(f"Drift Total Estimado: {total_drift_ms:.2f} ms")
            print(f"{'='*60}\n")
            return total_drift_ms
        else:
            print("Dados insuficientes para calcular drift.")
            return 0.0
    finally:
        if os.path.exists(temp_esq): os.remove(temp_esq)
        if os.path.exists(temp_dir): os.remove(temp_dir)

def gerar_video_calibrado(video_esq, video_dir, calib_file, offset_segundos, fps, duracao, output_file, encoder, preset, do_color_match=False):
    """Gera vídeo sincronizado E retificado (calibrado) usando OpenCV + FFmpeg Pipe."""
    print(f"Carregando calibração: {calib_file}")
    data = np.load(calib_file)
    mtx_l, dist_l = data['mtx_l'], data['dist_l']
    mtx_r, dist_r = data['mtx_r'], data['dist_r']
    R1, P1 = data['R1'], data['P1']
    R2, P2 = data['R2'], data['P2']

    cap_l = cv2.VideoCapture(video_esq)
    cap_r = cv2.VideoCapture(video_dir)
    w = int(cap_l.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap_l.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print("Calculando mapas de retificação...")
    map1_l, map2_l = cv2.initUndistortRectifyMap(mtx_l, dist_l, R1, P1, (w, h), cv2.CV_16SC2)
    map1_r, map2_r = cv2.initUndistortRectifyMap(mtx_r, dist_r, R2, P2, (w, h), cv2.CV_16SC2)

    # Sincronia (Seek)
    offset_frames = int(round(abs(offset_segundos) * fps))
    start_t_esq, start_t_dir = 0.0, 0.0
    if offset_segundos > 0:
        cap_l.set(cv2.CAP_PROP_POS_FRAMES, offset_frames)
        start_t_esq = offset_segundos
    else:
        cap_r.set(cv2.CAP_PROP_POS_FRAMES, offset_frames)
        start_t_dir = abs(offset_segundos)

    cmd = [
        "ffmpeg", "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{w*2}x{h}", "-pix_fmt", "bgr24", "-r", str(fps),
        "-i", "-", 
        "-ss", str(start_t_esq), "-i", video_esq,
        "-ss", str(start_t_dir), "-i", video_dir,
        "-filter_complex", "[1:a][2:a]amix=inputs=2[a]",
        "-map", "0:v", "-map", "[a]",
        "-c:v", encoder,
        "-pix_fmt", "yuv420p"
    ]

    if "qsv" in encoder:
        # Intel QuickSync
        cmd.extend(["-global_quality", "23", "-preset", "veryfast"])
    elif "nvenc" in encoder:
        cmd.extend(["-preset", "p1", "-rc", "constqp", "-qp", "23"])
    else:
        cmd.extend(["-preset", preset])

    cmd.extend(["-c:a", "aac"])
    if duracao:
        cmd.extend(["-t", str(duracao)])
    
    # Otimização para Streaming/VR: Move os metadados para o início do arquivo
    cmd.extend(["-movflags", "+faststart"])
    cmd.append(output_file)
    
    print(f"Iniciando processamento calibrado (Pipe FFmpeg)...")
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    
    try:
        frames_to_process = int(duracao * fps) if duracao else int(1e9)
        count = 0
        while count < frames_to_process:
            ret_l, frame_l = cap_l.read()
            ret_r, frame_r = cap_r.read()
            if not ret_l or not ret_r: break
            
            rect_l = cv2.remap(frame_l, map1_l, map2_l, cv2.INTER_LINEAR)
            rect_r = cv2.remap(frame_r, map1_r, map2_r, cv2.INTER_LINEAR)
            
            if do_color_match:
                rect_r = match_color_stats(rect_r, rect_l)
            
            frame_sbs = np.hstack((rect_l, rect_r))
            
            proc.stdin.write(frame_sbs.tobytes())
            count += 1
            if count % 60 == 0: print(f"Frames: {count}", end='\r')
    except BrokenPipeError:
        print("\n[ERRO] O processo FFmpeg foi encerrado inesperadamente.")
        print("       Isso geralmente ocorre por parâmetros de encoder inválidos ou resolução não suportada.")
        if "h264_qsv" in encoder and w*2 > 4096:
             print("       DICA: Para resoluções > 4K (como 5.4K), tente usar --encoder hevc_qsv")
        raise RuntimeError("FFmpeg Broken Pipe")
    finally:
        try:
            if proc.stdin: proc.stdin.close()
        except BrokenPipeError:
            pass
        proc.wait()
        cap_l.release()
        cap_r.release()

def gerar_video_sincronizado(video_esq, video_dir, offset_segundos, fps, duracao=None, drift_ms=0.0, total_duracao=None, encoder="libx264", preset="fast", fps_out=None, calib_file=None, output_file=None, do_color_match=False):
    """Gera o vídeo final lado a lado aplicando o corte necessário."""
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"data/output/videos_3d/video_3d_sincronizado_SBS_{timestamp}.mp4"
    
    # Garantir que o diretório de saída existe
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    if calib_file:
        try:
            return gerar_video_calibrado(video_esq, video_dir, calib_file, offset_segundos, fps, duracao, output_file, encoder, preset, do_color_match)
        except RuntimeError:
            print("\n[AUTO-FIX] Falha na codificação acelerada. Tentando fallback para CPU (libx264)...")
            # Fallback para CPU com preset ultrafast para não demorar uma eternidade
            return gerar_video_calibrado(video_esq, video_dir, calib_file, offset_segundos, fps, duracao, output_file, "libx264", "ultrafast", do_color_match)
    
    # Converter offset de tempo (segundos) para número exato de frames
    offset_frames = int(round(abs(offset_segundos) * fps))
    
    print(f"Offset detectado: {offset_segundos:.4f}s (~{offset_frames} frames)")
    
    # Lógica de Corte (Trim):
    # Correlação(Esq, Dir) -> Lag k
    # Se k > 0: O pico da Esquerda está num índice maior (acontece depois no arquivo).
    #           Isso significa que a Esquerda gravou mais tempo antes do evento (começou antes).
    #           Ação: Cortar o início da Esquerda.
    # Se k < 0: O pico da Direita está num índice maior. Direita começou antes.
    #           Ação: Cortar o início da Direita.
    if offset_segundos > 0:
        print(f"Ajuste: Cortando {offset_frames} frames do vídeo da ESQUERDA.")
        trim_esq = offset_frames
        trim_dir = 0
    else:
        print(f"Ajuste: Cortando {offset_frames} frames do vídeo da DIREITA.")
        trim_esq = 0
        trim_dir = offset_frames
        
    # Tempos de corte para o áudio (para manter sincronia com o vídeo)
    start_t_esq = trim_esq / fps
    start_t_dir = trim_dir / fps
    
    # Cálculo do Fator de Drift (Correção de Clock)
    # Se drift_ms > 0: Direita correu mais rápido (durou menos). Precisa ser esticada (fator > 1).
    drift_factor = 1.0
    if drift_ms != 0 and total_duracao:
        # duracao_dir_real = total_duracao - (drift_ms / 1000.0)
        # factor = total_duracao / duracao_dir_real
        dur_dir_real = total_duracao - (drift_ms / 1000.0)
        if dur_dir_real > 0:
            drift_factor = total_duracao / dur_dir_real
            print(f"Aplicando correção de Drift: {drift_ms}ms (Fator: {drift_factor:.8f})")

    # Configuração dos filtros de tempo
    # Vídeo: setpts multiplica o timestamp. Fator > 1 deixa o vídeo mais lento (estica).
    setpts_dir = f"(PTS-STARTPTS)*{drift_factor:.10f}" if drift_factor != 1.0 else "PTS-STARTPTS"
    
    # Áudio: atempo altera a velocidade. Se vídeo fica mais lento (fator > 1), áudio deve ficar mais lento (atempo < 1).
    # atempo = 1 / fator
    atempo_filter = f",atempo={1.0/drift_factor:.10f}" if drift_factor != 1.0 else ""

    # Filtro Complexo do FFmpeg:
    # 1. [0:v]trim...: Corta o vídeo da esquerda e reseta o relógio (PTS).
    # 2. [1:v]trim...: Corta o vídeo da direita e reseta o relógio.
    # 3. hstack: Empilha os dois vídeos horizontalmente (lado a lado).
    # 4. atrim/asetpts/amix: Faz o mesmo para o áudio e mistura os canais.
    filter_complex = (
        f"[0:v]trim=start_frame={trim_esq},setpts=PTS-STARTPTS[vl];"
        f"[1:v]trim=start_frame={trim_dir},setpts={setpts_dir}[vr];"
        f"[vl][vr]hstack[v];"
        f"[0:a]atrim=start={start_t_esq},asetpts=PTS-STARTPTS[al];"
        f"[1:a]atrim=start={start_t_dir},asetpts=PTS-STARTPTS{atempo_filter}[ar];"
        f"[al][ar]amix=inputs=2[a]"
    )
    
    cmd = [
        "ffmpeg", "-y", "-stats",
        "-i", video_esq,
        "-i", video_dir,
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "[a]",
        "-pix_fmt", "yuv420p",
    ]
    
    if duracao is not None:
        cmd.extend(["-t", str(duracao)])

    # Redução de FPS para compatibilidade com Quest/TV
    if fps_out:
        cmd.extend(["-r", str(fps_out)])

    # Configuração do Encoder
    cmd.extend(["-c:v", encoder])
    
    if "nvenc" in encoder:
        # Configurações otimizadas para NVIDIA GPU (p1 = mais rápido, p7 = melhor qualidade)
        # -rc constqp -qp 23 é similar ao CRF 23
        cmd.extend(["-preset", "p1", "-rc", "constqp", "-qp", "23"])
    elif "hevc_nvenc" in encoder:
        # NVIDIA HEVC (H.265) - Arquivos menores, melhor para Quest
        cmd.extend(["-preset", "p1", "-rc", "constqp", "-qp", "28"])
    elif "qsv" in encoder:
        # Intel QuickSync
        cmd.extend(["-global_quality", "23", "-preset", "veryfast"])
    elif encoder == "libx265":
        # CPU HEVC (Lento para gerar, mas ótimo para assistir)
        cmd.extend(["-crf", "28", "-preset", preset])
        # Adiciona tag para compatibilidade Apple/Quest em MP4
        cmd.extend(["-tag:v", "hvc1"])
    else:
        # Configurações padrão CPU (libx264)
        cmd.extend(["-crf", "23", "-preset", preset])

    # Otimização para Streaming/VR: Move os metadados para o início do arquivo
    cmd.extend(["-movflags", "+faststart"])

    cmd.extend(["-c:a", "aac", output_file])
    
    print(f"Gerando vídeo: {output_file} ...")
    print(f"Configuração: Encoder={encoder} | Preset={preset}")
    if fps_out:
        print(f"Convertendo taxa de quadros: {fps} -> {fps_out} fps")
    if duracao:
        print(f"Duração limitada a: {duracao} segundos")
    
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        print("\n[ERRO] Falha na codificação com FFmpeg.")
        if "nvenc" in encoder:
            print("[AUTO-FIX] Falha na GPU NVIDIA detectada. Tentando fallback para CPU (libx264, preset=ultrafast)...")
            gerar_video_sincronizado(video_esq, video_dir, offset_segundos, fps, duracao, drift_ms, total_duracao, encoder="libx264", preset="ultrafast", fps_out=fps_out, output_file=output_file, do_color_match=do_color_match)
        elif "qsv" in encoder:
            print("[AUTO-FIX] Falha no QuickSync (Intel) detectada. Tentando fallback para CPU (libx264, preset=ultrafast)...")
            gerar_video_sincronizado(video_esq, video_dir, offset_segundos, fps, duracao, drift_ms, total_duracao, encoder="libx264", preset="ultrafast", fps_out=fps_out, output_file=output_file, do_color_match=do_color_match)
        else:
            sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sincroniza vídeos pelo áudio.")
    parser.add_argument("esq", nargs="?", default="videos_gopro/LEFT.MP4", help="Caminho do vídeo da Esquerda")
    parser.add_argument("dir", nargs="?", default="videos_gopro/RIGHT.MP4", help="Caminho do vídeo da Direita")
    parser.add_argument("-t", "--duracao", type=float, help="Duração do vídeo de saída em segundos (opcional). Se omitido, gera completo.")
    parser.add_argument("--drift", type=float, default=0.0, help="Correção de drift em ms (Esq - Dir). Use se souber que as câmeras dessincronizam no final.")
    parser.add_argument("--auto-drift", action="store_true", help="Calcula e aplica o drift automaticamente analisando todo o vídeo.")
    parser.add_argument("--gpu", action="store_true", help="Usa aceleração de hardware NVIDIA (h264_nvenc).")
    parser.add_argument("--preset", default="fast", help="Velocidade do encoder CPU (ultrafast, superfast, fast, medium).")
    parser.add_argument("--encoder", default="libx264", help="Encoder manual (ex: h264_qsv).")
    parser.add_argument("--fps-out", type=int, help="Reduz o FPS do vídeo final (ex: 60) para compatibilidade com Quest/TV.")
    parser.add_argument("--calib", help="Arquivo .npz de calibração para retificar o vídeo.")
    parser.add_argument("--out", help="Caminho do arquivo de saída (opcional).")
    parser.add_argument("--offset-manual", type=float, help="Define o offset (segundos) manualmente, pulando a análise de áudio.")
    parser.add_argument("--match-color", action="store_true", help="Ajusta a cor da câmera direita para igualar a esquerda (corrige WB). Requer --calib.")
    args = parser.parse_args()

    p_esq = args.esq
    p_dir = args.dir
    
    # Lê FPS e Duração Total para cálculos
    cap = cv2.VideoCapture(p_esq)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    total_duracao = frame_count / fps if fps > 0 else 0
    cap.release()
    
    # 1. Calcular ou Definir Offset
    if args.offset_manual is not None:
        print(f"Usando offset manual fornecido: {args.offset_manual} segundos")
        offset = args.offset_manual
    else:
        print("Calculando sincronia inicial por áudio...")
        extrair_audio_temporario(p_esq, "temp_esq.wav", start_time=0, duracao=20)
        extrair_audio_temporario(p_dir, "temp_dir.wav", start_time=0, duracao=20)
        offset = calcular_atraso_audio("temp_esq.wav", "temp_dir.wav")
    
    # 3. Calcular Drift (se solicitado)
    drift_ms = args.drift
    if args.auto_drift:
        drift_ms = calcular_drift_automatico(p_esq, p_dir, total_duracao)
    
    # Definição do Encoder
    encoder_usado = args.encoder
    if args.gpu:
        encoder_usado = "h264_nvenc"

    # 3. Gerar vídeo
    gerar_video_sincronizado(p_esq, p_dir, offset, fps, duracao=args.duracao, drift_ms=drift_ms, total_duracao=total_duracao, encoder=encoder_usado, preset=args.preset, fps_out=args.fps_out, calib_file=args.calib, output_file=args.out, do_color_match=args.match_color)
    
    # Limpeza
    if os.path.exists("temp_esq.wav"): os.remove("temp_esq.wav")
    if os.path.exists("temp_dir.wav"): os.remove("temp_dir.wav")
    print("Concluído!")
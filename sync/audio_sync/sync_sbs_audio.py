# =============================================================================
# SCRIPT DE SINCRONIZAÇÃO POR ÁUDIO (SEM RETIFICAÇÃO ESTÉREO)
# =============================================================================
# Este script sincroniza dois vídeos (Esquerda e Direita) analisando a correlação
# entre suas faixas de áudio. Ele encontra o atraso temporal e pode gerar
# tanto um vídeo lado a lado (Side-by-Side) quanto uma sequência de frames
# sincronizados para conferência visual, além de frames PNG de alta qualidade
# para calibração de câmeras.
#
# FUNCIONALIDADES PRINCIPAIS:
# ===========================
#    • Sincronia Temporal: Alinha o início dos vídeos pelo áudio (palma/claquete).
#    • Correção de Drift: Compensa diferenças de relógio entre câmeras em vídeos longos.
#    • Geração de Vídeo Sincronizado: Cria saída SBS sem retificação de lente.
#    • Frames PNG para Calibração: Extrai frames em PNG (lossless) para uso posterior
#      no script de calibração de câmeras. Salva automaticamente em:
#      
#      <out>/
#      ├── esquerda/
#      │   ├── frame_000000_tXXX.XXs.png
#      │   └── ...
#      └── direita/
#          ├── frame_000000_tXXX.XXs.png
#          └── ...
#
# MODO DE USO:
# ============
#    python3 sync/audio_sync/sync_sbs_audio.py VIDEO_ESQ VIDEO_DIR --modo {frames_calib|frames_sbs|video_sync} --out DIRETORIO [OPCOES]
#
# ARGUMENTOS POSICIONAIS (OBRIGATÓRIOS):
# ======================================
#    VIDEO_ESQ              Caminho do vídeo da câmera Esquerda
#    VIDEO_DIR              Caminho do vídeo da câmera Direita
#
# ARGUMENTOS OBRIGATÓRIOS:
# ========================
#    --modo {frames_calib|frames_sbs|video_sync}
#                           Modo exclusivo de saída (apenas um por execução)
#                           'frames_calib' = salva pares PNG para calibração
#                           'frames_sbs'   = salva imagens JPG lado a lado
#                           'video_sync'   = gera vídeo MP4 SBS
#    --out DIRETORIO        Obrigatório em todos os modos
#                           video_sync: diretório do MP4 (nome automático: sbs_YYYYMMDD_HHMMSS.mp4)
#                           frames_*: diretório onde os frames serão salvos
#
# OPÇÕES DE SINCRONIZAÇÃO:
# ========================
#    -t, --duracao FLOAT    Duração máxima da saída em segundos
#                           Válido apenas com --modo video_sync
#    --offset-manual FLOAT  Define manualmente o offset (segundos) entre os vídeos
#                           Pula a análise de áudio se fornecido
#                           Exemplo: --offset-manual 2.5 (esquerda começa 2.5s depois)
#    --drift FLOAT          Correção manual de drift em milissegundos (Esq - Dir)
#                           Use se souber que as câmeras dessincronizam no final
#                           Exemplo: --drift 100 (direita correu 100ms mais rápido)
#    --auto-drift           Detecta e compensa drift automaticamente analisando
#                           amostras de áudio ao longo de todo o vídeo (lento)
#
# OPÇÕES DE FRAMES (--modo frames_sbs e --modo frames_calib):
# ============================================================
#    --step INT             Intervalo em frames para salvar imagens
#                           Padrão em frames_sbs: 2400 (~80s em 30fps)
#                           Padrão em frames_calib: 300 (~10s em 30fps)
#
# OPÇÕES DE FRAMES PNG PARA CALIBRAÇÃO (--modo frames_calib):
# ===========================================================
#    Os frames PNG são salvos em subpastas esquerda/ e direita/ dentro de --out
#    Dica: use --step 300-600 para menos imagens e processamento mais rápido
#
# OPÇÕES DE CODIFICAÇÃO DE VÍDEO:
# ================================
#    --encoder CODEC        Especificar codec manualmente (padrão: libx264)
#                           Exemplos: libx265, h264_qsv (Intel), h264_nvenc (NVIDIA)
#    --preset SPEED         Velocidade de codificação CPU: ultrafast, superfast,
#                           fast (padrão), medium. Mais rápido = qualidade menor
#    --fps-out INT          Reduz taxa de quadros do vídeo final (ex: 30, 60)
#                           Útil para compatibilidade com Quest/TV
#    --gpu                  Usa aceleração NVIDIA H.264 (h264_nvenc) se disponível
#
# OBSERVAÇÕES DE PERFORMANCE E QUALIDADE:
# ========================================
#    Velocidade (do mais rápido para o mais lento):
#    1. h264_nvenc (--gpu)     = GPU NVIDIA, muito rápido
#    2. h264_qsv               = GPU Intel QuickSync, rápido
#    3. libx264 (padrão)       = CPU, velocidade moderada, ótima compatibilidade
#    4. libx265                = CPU, mais lento mas melhor compressão
#
#    Qualidade:
#    • libx265 gera melhor compressão/qualidade por bitrate
#    • libx264 é ótimo compromisso entre qualidade e velocidade
#    • GPU encoders são mais rápidos mas ligeiramente menor qualidade perceptual
#    • PNG frames para calibração: SEMPRE lossless (máxima qualidade)
#
#    Dicas:
#    • Para vídeos QHD/4K: use --fps-out 30 e considere libx265 com --preset medium
#    • Para processamento rápido: use --gpu se tiver GPU NVIDIA
#    • Para calibração: use --modo frames_calib com --step 300-600
#    • Em Intel Iris Xe: prefira hevc_qsv se disponível (menor arquivo)
#
# ============================================================================
# EXEMPLOS DE USO
# ============================================================================
#
#    1. EXEMPLO BÁSICO - Sincronizar vídeos (gerar MP4 SBS):
#       python3 sync/audio_sync/sync_sbs_audio.py LEFT.MP4 RIGHT.MP4 \
#           --modo video_sync --out data/output/
#
#    2. GERAR FRAMES JPG SINCRONIZADOS (para verificação visual):
#       python3 sync/audio_sync/sync_sbs_audio.py LEFT.MP4 RIGHT.MP4 \
#           --modo frames_sbs --out data/frames_sync --step 300
#       → Salva frames lado a lado em JPG a cada 300 frames
#
#    3. TESTE RÁPIDO (duração limitada):
#       python3 sync/audio_sync/sync_sbs_audio.py LEFT.MP4 RIGHT.MP4 \
#           --modo video_sync --out data/output/ -t 60
#       → Processa apenas os primeiros 60 segundos
#
#    4. CORRIGIR DRIFT AUTOMÁTICO (vídeos longos >5 min):
#       python3 sync/audio_sync/sync_sbs_audio.py LEFT.MP4 RIGHT.MP4 \
#           --modo video_sync --out data/output/ --auto-drift
#       → Analisa o vídeo todo para detectar dessincronização progressiva
#
#    5. USAR GPU NVIDIA (muito mais rápido):
#       python3 sync/audio_sync/sync_sbs_audio.py LEFT.MP4 RIGHT.MP4 \
#           --modo video_sync --out data/output/ --gpu --preset ultrafast
#       → Usa aceleração por hardware NVIDIA
#
#    6. OFFSET MANUAL (sem análise de áudio):
#       python3 sync/audio_sync/sync_sbs_audio.py LEFT.MP4 RIGHT.MP4 \
#           --modo video_sync --out data/output/ --offset-manual 2.5
#       → Desalinha a esquerda em 2.5 segundos manualmente
#
#    7. SOMENTE FRAMES PNG PARA CALIBRAÇÃO:
#       python3 sync/audio_sync/sync_sbs_audio.py LEFT.MP4 RIGHT.MP4 \
#           --modo frames_calib --out data/calib_frames --step 300
#       → Extrai pares PNG sincronizados para calibração
#       → Estrutura de saída:
#          data/calib_frames/
#          ├── esquerda/
#          └── direita/
#
#    8. VÍDEO + QUALIDADE MÁXIMA (libx265):
#        python3 sync/audio_sync/sync_sbs_audio.py LEFT.MP4 RIGHT.MP4 \
#            --modo video_sync --out data/output/ \
#            --encoder libx265 --preset medium
#        → Vídeo com melhor compressão/qualidade por bitrate
#
# ============================================================================

import subprocess
import numpy as np
import os
import sys
import argparse
import cv2
from datetime import datetime

def tocar_sinal(erro=False):
    """Emite sinal sonoro via bell do terminal: 1 bipe = sucesso, 3 bipes = erro."""
    n = 3 if erro else 1
    for _ in range(n):
        print("\a", end="", flush=True)


def detectar_intel_iris_xe():
    """Detecta Intel Iris Xe via lspci, quando disponível."""
    try:
        resultado = subprocess.run(["lspci"], capture_output=True, text=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False

    saida = (resultado.stdout + resultado.stderr).lower()
    return "iris xe" in saida or "xe graphics" in saida


def ffmpeg_suporta_encoder(nome_encoder):
    """Verifica se o FFmpeg atual expõe um encoder específico."""
    try:
        resultado = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False

    saida = resultado.stdout.lower()
    return nome_encoder.lower() in saida

# Tenta importar scipy, se não tiver, avisa ou tenta instalar
try:
    from scipy.io import wavfile
    from scipy.signal import correlate
except ImportError:
    print("Biblioteca 'scipy' não encontrada. Instalando...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "scipy"])
    from scipy.io import wavfile
    from scipy.signal import correlate

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
    
    # 1. Normalização Inicial
    sig_esq = (sig_esq - np.mean(sig_esq)) / (np.std(sig_esq) + 1e-10)
    sig_dir = (sig_dir - np.mean(sig_dir)) / (np.std(sig_dir) + 1e-10)
    
    # 2. Realçar transientes (estalos/palmas)
    # A primeira derivada (np.diff) age como um filtro passa-alta, removendo
    # ruídos de baixa frequência (vento, motores) que podem enganar a correlação.
    sig_esq = np.abs(np.diff(sig_esq))
    sig_dir = np.abs(np.diff(sig_dir))

    # 3. Normalizar os envelopes de energia novamente
    sig_esq = (sig_esq - np.mean(sig_esq)) / (np.std(sig_esq) + 1e-10)
    sig_dir = (sig_dir - np.mean(sig_dir)) / (np.std(sig_dir) + 1e-10)

    # print("Correlacionando sinais de áudio...") # Comentado para não poluir no loop de drift
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
    
    # Em vídeos curtos, amostrar a cada 60s gera poucos pontos e não calcula regressão.
    # Esta lógica adapta a quantidade de amostras para manter robustez em ~1-3 minutos.
    janela = 8.0 if duracao_total <= 120 else 10.0
    max_start = max(0.0, duracao_total - janela)
    alvo_amostras = 5 if duracao_total <= 180 else 8

    if max_start == 0.0:
        amostras_inicio = [0.0]
    else:
        amostras_inicio = np.linspace(0.0, max_start, num=alvo_amostras).tolist()
    
    times = []
    delays = []
    
    temp_esq = "temp_drift_calc_esq.wav"
    temp_dir = "temp_drift_calc_dir.wav"
    
    try:
        for current_time in amostras_inicio:
            try:
                extrair_audio_temporario(video_esq, temp_esq, start_time=current_time, duracao=janela)
                extrair_audio_temporario(video_dir, temp_dir, start_time=current_time, duracao=janela)
                
                delay = calcular_atraso_audio(temp_esq, temp_dir)
                
                times.append(current_time)
                delays.append(delay)
                print(f"  T={current_time:6.1f}s | Delay={delay:8.5f}s")
            except Exception as e:
                print(f"  T={current_time:6.1f}s | Erro na leitura: {e}")
            
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

def gerar_frames_sincronizados(video_esq, video_dir, offset_segundos, fps, output_dir, step_frames=2400):
    """Gera frames lado a lado em intervalos fixos para conferência visual da sincronia."""
    print(f"Gerando frames sincronizados em: {output_dir}")
    os.makedirs(output_dir, exist_ok=True)

    cap_l = cv2.VideoCapture(video_esq)
    cap_r = cv2.VideoCapture(video_dir)

    total_frames_esq = int(cap_l.get(cv2.CAP_PROP_FRAME_COUNT))
    total_frames_dir = int(cap_r.get(cv2.CAP_PROP_FRAME_COUNT))
    fps_r = cap_r.get(cv2.CAP_PROP_FPS) or fps

    trim_esq = 0
    trim_dir = 0
    if offset_segundos > 0:
        # Offset positivo: O pico da Esquerda está num índice maior.
        # Cortar o início da esquerda.
        trim_esq = int(round(offset_segundos * fps))
    elif offset_segundos < 0:
        # Offset negativo: O pico da Direita está num índice maior. Cortar o início da direita.
        trim_dir = int(round(abs(offset_segundos) * fps_r))

    frame_idx_esq = trim_esq
    count = 0

    while frame_idx_esq < total_frames_esq:
        tempo_sync = (frame_idx_esq - trim_esq) / fps
        frame_idx_dir = trim_dir + int(round(tempo_sync * fps_r))

        if frame_idx_dir >= total_frames_dir:
            break

        cap_l.set(cv2.CAP_PROP_POS_FRAMES, frame_idx_esq)
        ret_l, frame_l = cap_l.read()

        cap_r.set(cv2.CAP_PROP_POS_FRAMES, frame_idx_dir)
        ret_r, frame_r = cap_r.read()

        if not ret_l or not ret_r:
            break

        if frame_l.shape[0] != frame_r.shape[0]:
            scale = frame_l.shape[0] / frame_r.shape[0]
            new_w = int(frame_r.shape[1] * scale)
            frame_r = cv2.resize(frame_r, (new_w, frame_l.shape[0]))

        combined = cv2.hconcat([frame_l, frame_r])
        tempo_esq_src = frame_idx_esq / fps
        tempo_dir_src = frame_idx_dir / fps_r
        info_text = f"E:{tempo_esq_src:.2f}s | D:{tempo_dir_src:.2f}s"
        cv2.putText(combined, info_text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

        fname = f"sync_{count:04d}_E{frame_idx_esq}_D{frame_idx_dir}.jpg"
        cv2.imwrite(os.path.join(output_dir, fname), combined)
        print(f"[{count}] Salvo: {fname}")

        frame_idx_esq += step_frames
        count += 1

    cap_l.release()
    cap_r.release()
    print("Concluído.")

def gerar_frames_calibracao_png(video_esq, video_dir, offset_segundos, fps, output_dir, step_frames=300):
    """
    Gera frames sincronizados em PNG (qualidade máxima lossless) para calibração de câmeras.
    Salva frames esquerdo e direito em subdiretórios separados.
    
    Parâmetros:
    - step_frames: intervalo em frames para extrair. Padrão 300 (~10s @ 30fps)
    """
    print(f"\n{'='*60}")
    print(f"GERANDO FRAMES PNG PARA CALIBRAÇÃO")
    print(f"{'='*60}")
    print(f"Destino: {output_dir}")
    print(f"Intervalo: {step_frames} frames (~{step_frames/fps:.1f}s @ {fps}fps)")
    
    # Criar subdiretórios para esquerda e direita
    dir_esq = os.path.join(output_dir, "esquerda")
    dir_dir = os.path.join(output_dir, "direita")
    os.makedirs(dir_esq, exist_ok=True)
    os.makedirs(dir_dir, exist_ok=True)

    cap_l = cv2.VideoCapture(video_esq)
    cap_r = cv2.VideoCapture(video_dir)

    total_frames_esq = int(cap_l.get(cv2.CAP_PROP_FRAME_COUNT))
    total_frames_dir = int(cap_r.get(cv2.CAP_PROP_FRAME_COUNT))
    fps_r = cap_r.get(cv2.CAP_PROP_FPS) or fps

    trim_esq = 0
    trim_dir = 0
    if offset_segundos > 0:
        trim_esq = int(round(offset_segundos * fps))
    elif offset_segundos < 0:
        trim_dir = int(round(abs(offset_segundos) * fps_r))

    frame_idx_esq = trim_esq
    count = 0

    print(f"Começando extração de frames...\n")

    while frame_idx_esq < total_frames_esq:
        tempo_sync = (frame_idx_esq - trim_esq) / fps
        frame_idx_dir = trim_dir + int(round(tempo_sync * fps_r))

        if frame_idx_dir >= total_frames_dir:
            break

        cap_l.set(cv2.CAP_PROP_POS_FRAMES, frame_idx_esq)
        ret_l, frame_l = cap_l.read()

        cap_r.set(cv2.CAP_PROP_POS_FRAMES, frame_idx_dir)
        ret_r, frame_r = cap_r.read()

        if not ret_l or not ret_r:
            break

        # Salvar frames em PNG com máxima qualidade (lossless)
        # PNG_COMPRESSION_LEVEL 0 = sem compressão (mais rápido)
        # PNG_COMPRESSION_LEVEL 9 = máxima compressão
        # Para calibração, usar 0 (sem perda de qualidade)
        tempo_esq_src = frame_idx_esq / fps
        tempo_dir_src = frame_idx_dir / fps_r
        fname_esq = f"frame_{count:06d}_t{tempo_esq_src:08.2f}s.png"
        fname_dir = f"frame_{count:06d}_t{tempo_dir_src:08.2f}s.png"
        
        path_esq = os.path.join(dir_esq, fname_esq)
        path_dir = os.path.join(dir_dir, fname_dir)
        
        # Salvar com máxima qualidade (PNG é lossless)
        cv2.imwrite(path_esq, frame_l, [cv2.IMWRITE_PNG_COMPRESSION, 0])
        cv2.imwrite(path_dir, frame_r, [cv2.IMWRITE_PNG_COMPRESSION, 0])
        
        if (count + 1) % 10 == 0:
            print(f"[{count+1}] Frames salvos | T={tempo_esq_src:7.2f}s - {tempo_dir_src:7.2f}s")

        frame_idx_esq += step_frames
        count += 1

    cap_l.release()
    cap_r.release()
    
    print(f"\n{'='*60}")
    print(f"✓ Extração concluída!")
    print(f"  Total de pares: {count}")
    print(f"  Esquerda: {dir_esq}")
    print(f"  Direita:  {dir_dir}")
    print(f"{'='*60}\n")

def gerar_video_sincronizado(video_esq, video_dir, offset_segundos, fps, duracao=None, drift_ms=0.0, total_duracao=None, encoder="libx264", preset="fast", fps_out=None, output_file=None):
    """Gera o vídeo final lado a lado aplicando o corte necessário."""
    # Garantir que o diretório de saída existe
    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
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
            gerar_video_sincronizado(video_esq, video_dir, offset_segundos, fps, duracao, drift_ms, total_duracao, encoder="libx264", preset="ultrafast", fps_out=fps_out, output_file=output_file)
        elif "qsv" in encoder:
            print("[AUTO-FIX] Falha no QuickSync (Intel) detectada. Tentando fallback para CPU (libx264, preset=ultrafast)...")
            gerar_video_sincronizado(video_esq, video_dir, offset_segundos, fps, duracao, drift_ms, total_duracao, encoder="libx264", preset="ultrafast", fps_out=fps_out, output_file=output_file)
        else:
            tocar_sinal(erro=True)
            sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sincroniza vídeos pelo áudio.")
    parser.add_argument("esq", help="Caminho do vídeo da câmera Esquerda")
    parser.add_argument("dir", help="Caminho do vídeo da câmera Direita")
    parser.add_argument(
        "--modo",
        choices=["frames_calib", "frames_sbs", "video_sync"],
        required=True,
        help="Modo exclusivo de processamento: 'frames_calib', 'frames_sbs' ou 'video_sync'.",
    )
    parser.add_argument("-t", "--duracao", type=float, help="Duração da saída em segundos (apenas para --modo video_sync).")
    parser.add_argument("--drift", type=float, default=0.0, help="Correção de drift em ms (Esq - Dir). Use se souber que as câmeras dessincronizam no final.")
    parser.add_argument("--auto-drift", action="store_true", help="Calcula e aplica o drift automaticamente analisando todo o vídeo.")
    parser.add_argument("--gpu", action="store_true", help="Usa aceleração de hardware NVIDIA (h264_nvenc).")
    parser.add_argument("--preset", default="fast", help="Velocidade do encoder CPU (ultrafast, superfast, fast, medium).")
    parser.add_argument("--encoder", default="libx264", help="Encoder manual (ex: h264_qsv). (melhor qualidade: libx265 com --preset medium)")
    parser.add_argument("--fps-out", type=int, help="Reduz o FPS do vídeo final (ex: 60) para compatibilidade com Quest/TV.")
    parser.add_argument("--out", required=True, help="Diretório de saída (obrigatório em todos os modos).")
    parser.add_argument("--step", type=int, help="Intervalo em frames (apenas para --modo frames_calib e --modo frames_sbs).")
    parser.add_argument("--offset-manual", type=float, help="Define o offset (segundos) manualmente, pulando a análise de áudio.")
    args = parser.parse_args()

    # Regras de modo exclusivo para simplificar processamento e reduzir falhas.
    if args.modo == "video_sync":
        if args.step is not None:
            parser.error("--step só pode ser usado com --modo frames_calib ou --modo frames_sbs.")
    else:
        if args.duracao is not None:
            parser.error("--duracao só pode ser usado com --modo video_sync.")

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
        extrair_audio_temporario(p_esq, "temp_esq.wav", start_time=0, duracao=40)
        extrair_audio_temporario(p_dir, "temp_dir.wav", start_time=0, duracao=40)
        offset = calcular_atraso_audio("temp_esq.wav", "temp_dir.wav")
    
    # 3. Calcular Drift (se solicitado)
    drift_ms = args.drift
    if args.auto_drift:
        drift_ms = calcular_drift_automatico(p_esq, p_dir, total_duracao)
    
    # Definição do Encoder
    encoder_usado = args.encoder
    if args.gpu:
        encoder_usado = "h264_nvenc"
    elif encoder_usado == "libx264" and detectar_intel_iris_xe():
        if ffmpeg_suporta_encoder("hevc_qsv"):
            print("Intel Iris Xe detectada. Usando encoder hevc_qsv para menor tamanho.")
            encoder_usado = "hevc_qsv"
        elif ffmpeg_suporta_encoder("h264_qsv"):
            print("Intel Iris Xe detectada. Usando encoder h264_qsv.")
            encoder_usado = "h264_qsv"

    # 3. Gerar saída com modo exclusivo
    if args.modo == "frames_sbs":
        step_frames = args.step if args.step is not None else 2400
        output_dir = args.out
        gerar_frames_sincronizados(p_esq, p_dir, offset, fps, output_dir, step_frames=step_frames)
    elif args.modo == "frames_calib":
        step_frames_calib = args.step if args.step is not None else 300
        output_calib_dir = args.out
        gerar_frames_calibracao_png(p_esq, p_dir, offset, fps, output_calib_dir, step_frames=step_frames_calib)
    else:  # video_sync
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(args.out, f"sbs_{timestamp}.mp4")
        gerar_video_sincronizado(p_esq, p_dir, offset, fps, duracao=args.duracao, drift_ms=drift_ms, total_duracao=total_duracao, encoder=encoder_usado, preset=args.preset, fps_out=args.fps_out, output_file=output_file)
    
    # Limpeza
    if os.path.exists("temp_esq.wav"): os.remove("temp_esq.wav")
    if os.path.exists("temp_dir.wav"): os.remove("temp_dir.wav")
    tocar_sinal()
    print("Concluído!")
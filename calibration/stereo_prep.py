import os
import subprocess
import tempfile

import cv2
import numpy as np


def extrair_audio_temporario(video_path, audio_out, start_time=0, duracao=20):
    """Extrai um trecho de audio do video para analise."""
    if os.path.exists(audio_out):
        os.remove(audio_out)

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        str(start_time),
        "-i",
        video_path,
        "-t",
        str(duracao),
        "-ac",
        "1",
        "-ar",
        "16000",
        audio_out,
    ]
    subprocess.run(cmd, check=True)


def calcular_atraso_audio(wav_esq, wav_dir):
    """Calcula o lag entre dois audios com correlacao cruzada (FFT)."""
    from scipy.io import wavfile
    from scipy.signal import correlate

    rate, sig_esq = wavfile.read(wav_esq)
    _, sig_dir = wavfile.read(wav_dir)

    sig_esq = (sig_esq - np.mean(sig_esq)) / (np.std(sig_esq) + 1e-10)
    sig_dir = (sig_dir - np.mean(sig_dir)) / (np.std(sig_dir) + 1e-10)

    correlation = correlate(sig_esq, sig_dir, mode="full", method="fft")
    lags = np.arange(-len(sig_dir) + 1, len(sig_esq))

    lag_idx = np.argmax(correlation)
    lag_samples = lags[lag_idx]
    return lag_samples / rate


def calcular_drift_automatico(video_esq, video_dir, duracao_total):
    """Calcula drift total estimado (ms) com amostras ao longo do video."""
    print("Calculando drift automatico (pode levar um minuto)...")

    intervalo = 60.0
    janela = 10.0
    times = []
    delays = []
    current_time = 0.0

    tmp1 = tempfile.NamedTemporaryFile(suffix="_drift_e.wav", delete=False)
    tmp2 = tempfile.NamedTemporaryFile(suffix="_drift_d.wav", delete=False)
    tmp1.close()
    tmp2.close()

    try:
        while current_time + janela < duracao_total:
            try:
                extrair_audio_temporario(video_esq, tmp1.name, start_time=current_time, duracao=janela)
                extrair_audio_temporario(video_dir, tmp2.name, start_time=current_time, duracao=janela)
                delay = calcular_atraso_audio(tmp1.name, tmp2.name)
                times.append(current_time)
                delays.append(delay)
                print(f"  T={current_time:6.1f}s | Delay={delay:8.5f}s")
            except Exception:
                pass
            current_time += intervalo

        if len(times) > 1:
            slope = np.polyfit(times, delays, 1)[0]
            total_drift_ms = (slope * duracao_total) * 1000.0
            print(f"Drift Total Estimado: {total_drift_ms:.2f} ms")
            return total_drift_ms
        return 0.0
    finally:
        if os.path.exists(tmp1.name):
            os.remove(tmp1.name)
        if os.path.exists(tmp2.name):
            os.remove(tmp2.name)


def extrair_frames_sincronizados(
    video_esq,
    video_dir,
    output_dir,
    offset,
    drift_ms=0.0,
    intervalo=60,
    ext="jpg",
):
    """Extrai pares de frames alinhados aplicando offset e drift."""
    os.makedirs(output_dir, exist_ok=True)

    cap_esq = cv2.VideoCapture(video_esq)
    cap_dir = cv2.VideoCapture(video_dir)

    fps = cap_esq.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap_esq.get(cv2.CAP_PROP_FRAME_COUNT))
    duracao_total = total_frames / fps

    drift_factor = 1.0
    if drift_ms != 0:
        dur_dir_real = duracao_total - (drift_ms / 1000.0)
        if dur_dir_real > 0:
            drift_factor = duracao_total / dur_dir_real

    print(f"\n{'=' * 60}")
    print("EXTRAINDO FRAMES SINCRONIZADOS")
    print(f"{'=' * 60}")
    print(f"Offset Inicial: {offset:.5f}s")
    print(f"Drift Factor:   {drift_factor:.8f}")
    print(f"Intervalo:      A cada {intervalo} frames")
    print(f"Saida:          {output_dir}/")

    saved_count = 0
    frame_idx = 0

    start_time_esq = offset if offset > 0 else 0
    start_time_dir = abs(offset) if offset < 0 else 0

    while True:
        target_frame_esq = frame_idx
        if target_frame_esq >= total_frames:
            break

        tempo_relativo = frame_idx / fps
        ts_esq = start_time_esq + tempo_relativo
        ts_dir = start_time_dir + (tempo_relativo / drift_factor)

        cap_esq.set(cv2.CAP_PROP_POS_MSEC, ts_esq * 1000.0)
        ret_e, img_e = cap_esq.read()

        cap_dir.set(cv2.CAP_PROP_POS_MSEC, ts_dir * 1000.0)
        ret_d, img_d = cap_dir.read()

        if ret_e and ret_d:
            nome_l = os.path.join(output_dir, f"frame_{saved_count:04d}_L.{ext}")
            nome_r = os.path.join(output_dir, f"frame_{saved_count:04d}_R.{ext}")
            cv2.imwrite(nome_l, img_e)
            cv2.imwrite(nome_r, img_d)

            print(
                f"[{saved_count:03d}] T_Sync: {tempo_relativo:.2f}s | "
                f"E: {ts_esq:.3f}s | D: {ts_dir:.3f}s -> Salvo"
            )
            saved_count += 1
        else:
            print(f"Fim do video ou erro de leitura em T={tempo_relativo:.2f}s")
            if not ret_e and not ret_d:
                break

        frame_idx += intervalo

    cap_esq.release()
    cap_dir.release()
    print(f"Concluido! {saved_count} pares salvos em '{output_dir}'.")


def preparar_calibracao_stereo(
    video_esq,
    video_dir,
    output_dir,
    intervalo=60,
    auto_drift=False,
    ext="jpg",
):
    """Executa pipeline completo: offset por audio, drift opcional e extracao."""
    temp_esq = tempfile.NamedTemporaryFile(suffix="_sync_e.wav", delete=False)
    temp_dir = tempfile.NamedTemporaryFile(suffix="_sync_d.wav", delete=False)
    temp_esq.close()
    temp_dir.close()

    try:
        print("--- Passo 1: Sincronia de Audio ---")

        cap = cv2.VideoCapture(video_esq)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        duracao_total = frames / fps
        cap.release()

        extrair_audio_temporario(video_esq, temp_esq.name, start_time=0, duracao=20)
        extrair_audio_temporario(video_dir, temp_dir.name, start_time=0, duracao=20)

        offset = calcular_atraso_audio(temp_esq.name, temp_dir.name)
        print(f"Offset detectado: {offset:.5f} segundos")

        drift_ms = 0.0
        if auto_drift:
            print("\n--- Passo 2: Calculo de Drift ---")
            drift_ms = calcular_drift_automatico(video_esq, video_dir, duracao_total)

        extrair_frames_sincronizados(video_esq, video_dir, output_dir, offset, drift_ms, intervalo, ext=ext)
    finally:
        if os.path.exists(temp_esq.name):
            os.remove(temp_esq.name)
        if os.path.exists(temp_dir.name):
            os.remove(temp_dir.name)

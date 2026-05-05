import cv2
import argparse
import os
import sys


def resolve_output_dir(video_path, output_dir, default_dir_name):
    if output_dir:
        if os.path.isabs(output_dir) or os.path.dirname(output_dir):
            return output_dir
        return os.path.join(os.path.dirname(os.path.abspath(video_path)), output_dir)
    return os.path.join(os.path.dirname(os.path.abspath(video_path)), default_dir_name)

def gerar_frames_sync(video_esq, video_dir, ajuste, drift_ms, step_frames=2400, output_dir=None):
    if not os.path.exists(video_esq) or not os.path.exists(video_dir):
        print("Erro: Vídeos não encontrados.")
        return

    cap_esq = cv2.VideoCapture(video_esq)
    cap_dir = cv2.VideoCapture(video_dir)

    fps_esq = cap_esq.get(cv2.CAP_PROP_FPS)
    fps_dir = cap_dir.get(cv2.CAP_PROP_FPS)
    
    total_frames_esq = int(cap_esq.get(cv2.CAP_PROP_FRAME_COUNT))
    duracao_esq = total_frames_esq / fps_esq
    
    # Calcula o drift_factor baseado no drift em ms total sobre a duração do vídeo
    # drift_ms = (duracao_esq - duracao_dir) * 1000
    # duracao_dir = duracao_esq - (drift_ms / 1000.0)
    # drift_factor = duracao_esq / duracao_dir
    
    duracao_dir_estimada = duracao_esq - (drift_ms / 1000.0)
    drift_factor = 1.0
    if duracao_dir_estimada > 0:
        drift_factor = duracao_esq / duracao_dir_estimada
    
    output_dir = resolve_output_dir(video_esq, output_dir, "frames_sync")
    os.makedirs(output_dir, exist_ok=True)
    print(f"{'='*60}")
    print(f"GERADOR DE FRAMES SINCRONIZADOS (VALIDAÇÃO)")
    print(f"{'='*60}")
    print(f"Esq: {video_esq} ({fps_esq:.2f} fps)")
    print(f"Dir: {video_dir} ({fps_dir:.2f} fps)")
    print(f"Ajuste (Offset): {ajuste} s")
    print(f"Drift Total:     {drift_ms} ms")
    print(f"Drift Factor:    {drift_factor:.8f}")
    print(f"Output:          {output_dir}")
    print(f"{'-'*60}")

    frame_idx_esq = 0
    count = 0
    
    while frame_idx_esq < total_frames_esq:
        # Tempo atual no vídeo Esquerdo (Referência)
        tempo_esq = frame_idx_esq / fps_esq
        
        # Calcula tempo correspondente no vídeo Direito
        # Fórmula: Tempo_Dir = (Tempo_Esq + Ajuste) / Drift_Factor
        # Explicação:
        # 1. (Tempo_Esq + Ajuste): Aplica o deslocamento inicial.
        # 2. / Drift_Factor: Compensa a velocidade diferente do relógio da Direita.
        tempo_dir = (tempo_esq + ajuste) / drift_factor
        
        frame_idx_dir = int(tempo_dir * fps_dir)
        
        # Seek e Leitura
        cap_esq.set(cv2.CAP_PROP_POS_FRAMES, frame_idx_esq)
        ret_e, img_e = cap_esq.read()
        
        cap_dir.set(cv2.CAP_PROP_POS_FRAMES, frame_idx_dir)
        ret_d, img_d = cap_dir.read()
        
        if ret_e and ret_d:
            # Resize para garantir altura igual (baseado na esquerda) para o hconcat
            if img_e.shape[0] != img_d.shape[0]:
                scale = img_e.shape[0] / img_d.shape[0]
                new_w = int(img_d.shape[1] * scale)
                img_d = cv2.resize(img_d, (new_w, img_e.shape[0]))
            
            # Combina lado a lado
            combined = cv2.hconcat([img_e, img_d])
            
            # Desenha info no frame para facilitar a leitura
            info_text = f"E:{tempo_esq:.2f}s | D:{tempo_dir:.2f}s"
            cv2.putText(combined, info_text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
            
            fname = f"sync_{count:04d}_E{frame_idx_esq}_D{frame_idx_dir}.jpg"
            out_path = os.path.join(output_dir, fname)
            cv2.imwrite(out_path, combined)
            print(f"[{count}] Salvo: {fname} | T_Esq: {tempo_esq:.2f}s -> T_Dir: {tempo_dir:.2f}s")
            count += 1
        else:
            break
        
        frame_idx_esq += step_frames

    cap_esq.release()
    cap_dir.release()
    print("Concluído.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera frames lado a lado aplicando ajuste e drift calculados manualmente.")
    parser.add_argument("--esq", required=True, help="Vídeo Esquerda")
    parser.add_argument("--dir", required=True, help="Vídeo Direita")
    parser.add_argument("--ajuste", type=float, required=True, help="Ajuste inicial (Offset) em segundos")
    parser.add_argument("--drift", type=float, default=0.0, help="Drift Total em ms (Esq - Dir)")
    parser.add_argument("--step", type=int, default=2400, help="Intervalo de frames (padrão: 2400)")
    parser.add_argument("--out", help="Pasta de saída. Se omitido, salva ao lado do vídeo esquerdo.")
    
    args = parser.parse_args()
    
    gerar_frames_sync(args.esq, args.dir, args.ajuste, args.drift, args.step, args.out)
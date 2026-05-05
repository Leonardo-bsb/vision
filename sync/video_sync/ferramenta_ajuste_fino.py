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

def parse_tempo(t_str):
    if ":" in t_str:
        parts = t_str.split(":")
        return float(parts[0]) * 60 + float(parts[1])
    return float(t_str)

def gerar_grade_drift(video_esq, video_dir, timestamp, ajuste_fixo, centro_drift, step_drift, count, output_dir):
    if not os.path.exists(video_esq) or not os.path.exists(video_dir):
        print("Erro: Vídeos não encontrados.")
        return

    cap_esq = cv2.VideoCapture(video_esq)
    cap_dir = cv2.VideoCapture(video_dir)
    
    fps_esq = cap_esq.get(cv2.CAP_PROP_FPS)
    fps_dir = cap_dir.get(cv2.CAP_PROP_FPS)
    
    # Necessário para calcular o fator de drift
    total_frames_esq = int(cap_esq.get(cv2.CAP_PROP_FRAME_COUNT))
    duracao_total_esq = total_frames_esq / fps_esq
    
    # Tempo alvo no vídeo da esquerda
    t_target = parse_tempo(timestamp)
    frame_esq_target = int(t_target * fps_esq)
    
    output_dir = resolve_output_dir(video_esq, output_dir, "ajuste_fino_drift")
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"{'='*60}")
    print(f"FERRAMENTA DE AJUSTE FINO (BRACKETING DE DRIFT)")
    print(f"{'='*60}")
    print(f"Alvo (Esq):    {t_target}s")
    print(f"Ajuste Fixo:   {ajuste_fixo}s")
    print(f"Centro Drift:  {centro_drift} ms")
    print(f"Variação:      +/- {count} passos de {step_drift} ms")
    print(f"Duração Total: {duracao_total_esq:.2f}s (Ref. para cálculo)")
    print(f"{'-'*60}")

    # Gera variações
    for i in range(-count, count + 1):
        # O drift testado nesta iteração
        drift_teste = centro_drift + (i * step_drift)
        
        # Calcula o fator de drift correspondente
        duracao_dir_estimada = duracao_total_esq - (drift_teste / 1000.0)
        drift_factor = 1.0 if duracao_dir_estimada <= 0 else duracao_total_esq / duracao_dir_estimada
            
        # Calcula onde estaria o frame da direita com esse drift
        t_dir_estimado = (t_target + ajuste_fixo) / drift_factor
        frame_dir_target = int(t_dir_estimado * fps_dir)
        
        # Leitura dos frames
        cap_esq.set(cv2.CAP_PROP_POS_FRAMES, frame_esq_target)
        ret_e, img_e = cap_esq.read()
        
        cap_dir.set(cv2.CAP_PROP_POS_FRAMES, frame_dir_target)
        ret_d, img_d = cap_dir.read()
        
        if ret_e and ret_d:
            # Resize se necessário para garantir altura igual
            if img_e.shape[0] != img_d.shape[0]:
                scale = img_e.shape[0] / img_d.shape[0]
                new_w = int(img_d.shape[1] * scale)
                img_d = cv2.resize(img_d, (new_w, img_e.shape[0]))
            
            combined = cv2.hconcat([img_e, img_d])
            
            # Texto informativo na imagem
            cor = (0, 255, 0) if i == 0 else (0, 255, 255) # Verde no centro, Amarelo nas pontas
            texto = f"Drift: {drift_teste:+.1f}ms"
            cv2.putText(combined, texto, (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 2.0, cor, 4)
            
            # Nome do arquivo ordenável
            # Ex: grade_00_drift_100.0ms.jpg
            idx_str = f"{i+count:02d}" 
            fname = f"grade_{idx_str}_drift_{drift_teste:.1f}ms.jpg"
            
            out_path = os.path.join(output_dir, fname)
            cv2.imwrite(out_path, combined)
            print(f"Salvo: {fname} | Drift Factor: {drift_factor:.6f}")
            
    cap_esq.release()
    cap_dir.release()
    print(f"{'-'*60}")
    print(f"Verifique as imagens em: {output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera uma grade de imagens variando o DRIFT para encontrar a sincronia perfeita no final do vídeo.")
    parser.add_argument("--esq", required=True, help="Vídeo Esquerda")
    parser.add_argument("--dir", required=True, help="Vídeo Direita")
    parser.add_argument("--time", required=True, help="Tempo do evento no vídeo Esq (MM:SS ou Segundos)")
    parser.add_argument("--ajuste", type=float, required=True, help="Ajuste inicial fixo (s) já determinado")
    parser.add_argument("--drift", type=float, default=0.0, help="Drift central estimado em ms (Esq - Dir)")
    parser.add_argument("--step", type=float, default=10.0, help="Passo da variação do drift em ms")
    parser.add_argument("--count", type=int, default=5, help="Quantas variações para cada lado")
    parser.add_argument("--out", help="Pasta de saída. Se omitido, salva ao lado do vídeo esquerdo.")
    
    args = parser.parse_args()
    
    gerar_grade_drift(args.esq, args.dir, args.time, args.ajuste, args.drift, args.step, args.count, args.out)
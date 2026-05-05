import argparse
from datetime import datetime, timedelta

def parse_tempo(t_str):
    """
    Converte string de tempo (MM:SS.ms ou SS.ms) para segundos (float).
    Exemplos: "10:05.500" -> 605.5 | "45.2" -> 45.2
    """
    try:
        if ":" in t_str:
            partes = t_str.split(":")
            minutos = int(partes[0])
            segundos = float(partes[1])
            return (minutos * 60) + segundos
        else:
            return float(t_str)
    except ValueError:
        print(f"Erro: Formato de tempo inválido: {t_str}")
        exit(1)

def calcular_parametros(start_esq, start_dir, end_esq, end_dir):
    # 1. Converter inputs para segundos
    t_start_e = parse_tempo(start_esq)
    t_start_d = parse_tempo(start_dir)
    t_end_e = parse_tempo(end_esq)
    t_end_d = parse_tempo(end_dir)

    print(f"{'='*60}")
    print(f"CÁLCULO DE SINCRONIA MANUAL (CRONÔMETRO)")
    print(f"{'='*60}")
    print(f"ESQUERDA: Início={t_start_e:.3f}s | Fim={t_end_e:.3f}s")
    print(f"DIREITA:  Início={t_start_d:.3f}s | Fim={t_end_d:.3f}s")
    print(f"{'-'*60}")

    # 2. Calcular Ajuste Inicial (Offset)
    # Lógica: Se Esq=10s e Dir=12s, a Direita começou "depois" no relógio do mundo (perdeu 2s de gravação?)
    # Não, se o frame 0 mostra 10s na Esq e 12s na Dir:
    # Significa que a Direita começou a gravar quando o cronômetro JÁ ESTAVA em 12s.
    # A Esquerda começou quando estava em 10s.
    # A Esquerda gravou 2 segundos A MAIS no início.
    # Diferença = Esq - Dir.
    # Se (Esq - Dir) < 0: Esq=10, Dir=12 -> -2. Significa que Dir está adiantada no tempo absoluto.
    
    diff_inicial = t_start_e - t_start_d
    diff_inicial_ms = diff_inicial * 1000.0
    
    print(f"1. AJUSTE INICIAL (--ajuste)")
    print(f"   Diferença (Esq - Dir): {diff_inicial_ms:+.4f} ms ({diff_inicial:+.4f} s)")
    
    if diff_inicial > 0:
        print(f"   -> A Esquerda começou DEPOIS. Cortar {abs(diff_inicial_ms):.2f}ms da DIREITA.")
    elif diff_inicial < 0:
        print(f"   -> A Direita começou DEPOIS. Cortar {abs(diff_inicial_ms):.2f}ms da ESQUERDA.")
    else:
        print(f"   -> Vídeos perfeitamente sincronizados no início.")

    # 3. Calcular Drift (Variação de Velocidade)
    duracao_e = t_end_e - t_start_e
    duracao_d = t_end_d - t_start_d
    
    drift_ms = (duracao_e - duracao_d) * 1000.0

    print(f"\n2. DRIFT (Diferença de Duração)")
    print(f"   Duração medida pela ESQUERDA: {duracao_e:.4f}s")
    print(f"   Duração medida pela DIREITA:  {duracao_d:.4f}s")
    print(f"   Drift Total (Esq - Dir):      {drift_ms:+.4f} ms")
    
    if abs(drift_ms) < 1.0:
        print("   -> Sem drift perceptível (< 1ms).")
    else:
        if drift_ms > 0:
            print("   -> A Direita correu mais RÁPIDO (durou menos). Precisa ser ESTICADA.")
        else:
            print("   -> A Direita correu mais LENTO (durou mais). Precisa ser ENCOLHIDA.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calcula ajuste e drift baseando-se em tempos visuais (cronômetro).")
    parser.add_argument("--start_esq", required=True, help="Tempo no frame inicial da Esquerda (ex: 10:05.0)")
    parser.add_argument("--start_dir", required=True, help="Tempo no frame inicial da Direita (ex: 10:05.0)")
    parser.add_argument("--end_esq", required=True, help="Tempo no frame final da Esquerda")
    parser.add_argument("--end_dir", required=True, help="Tempo no frame final da Direita")
    
    args = parser.parse_args()
    calcular_parametros(args.start_esq, args.start_dir, args.end_esq, args.end_dir)
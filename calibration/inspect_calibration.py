import numpy as np
import os

def inspect_npz(file_path):
    if not os.path.exists(file_path):
        print(f"Erro: Arquivo não encontrado em {file_path}")
        return

    try:
        # Carrega o arquivo .npz
        data = np.load(file_path)
        print(f"=== Inspecionando: {os.path.basename(file_path)} ===")
        print(f"Caminho completo: {file_path}")
        print(f"Chaves encontradas: {data.files}")
        
        for key in data.files:
            array = data[key]
            print(f"\n--- Chave: '{key}' ---")
            print(f"Shape: {array.shape}")
            print(f"Tipo: {array.dtype}")
            print("Dados (resumo):")
            print(array)
            
    except Exception as e:
        print(f"Erro ao ler o arquivo .npz: {e}")

if __name__ == "__main__":
    target_path = "/home/leo/linguagens/tennisclub/data/calibration/nzd_files/dados_calibracao.npz"
    inspect_npz(target_path)
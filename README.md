# Vision

Workspace de visão computacional para calibração, sincronização e análise de vídeo estéreo.

Este repositório reúne ferramentas voltadas para:

- calibração mono e estéreo de câmeras;
- sincronização de vídeos (por áudio, metadata e flash);
- rastreamento de bola e medições cinemáticas;
- utilitários de inspeção/diagnóstico para vídeo e áudio;
- experimentos de reconstrução e análise 3D.

## Como começar

Pré-requisitos principais:

- Python 3.10+;
- FFmpeg (para rotinas de áudio e vídeo);
- OpenCV e NumPy no ambiente Python.

Instalação sugerida (ambiente virtual no Linux):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install opencv-python numpy scipy
```

Se quiser instalar o pacote compartilhado `cv_tools` em modo de desenvolvimento:

```bash
pip install -e cv_tools
```

Para detalhes operacionais da calibracao, consulte `calibration/CALIB.md`.

## Fluxo rápido recomendado

1. Preparar pares estéreo sincronizados para calibração.
2. Rodar calibração mono/estéreo e validar erro de reprojeção.
3. Sincronizar vídeos finais (áudio/metadata/flash).
4. Executar rastreamento/medições (velocidade, RPM, etc).
5. Validar qualidade com utilitários (nitidez, metadata, sincronia).

## Módulos do repositório

### `cv_tools/`
Pacote Python compartilhado para utilidades de calibração e visão computacional.

- Dependências declaradas em `pyproject.toml`: OpenCV, NumPy e SciPy.
- Serve como ponto de empacotamento para utilidades compartilhadas do workspace.
- A implementacao canonica de calibracao agora esta em `calibration/`.

### `calibration/`
Modulo independente de calibracao mono e estereo.

- `calibrar_camera.py`: calibracao intrinseca de camera unica.
- `gerar_tabuleiro.py`: gera/auxilia o padrao de tabuleiro para calibracao.
- `chessboard.py`: operações relacionadas ao padrão de tabuleiro.
- `stereo_calibration.py`: rotinas de calibração estéreo.
- `stereo_prep.py`: preparo de material para calibração estéreo.
- `visualizar_distorcao.py`: visualiza efeito de distorcao/correcao das lentes.
- `CALIB.md`: documentacao detalhada do fluxo de calibracao.

## Refatoração de duplicados

Os scripts duplicados entre `tennisclub` e `z-shelf` foram consolidados progressivamente em `calibration`.

- Duplicado consolidado (preparo/sincronia):
	- `z-shelf/src/preparar_calibracao_stereo.py`
	- O fluxo comum agora vive em `calibration/stereo_prep.py`.

- Duplicado reduzido (calibração):
	- `z-shelf/src/calibrar_cameras.py`
	- A calibracao central passou a reutilizar helpers comuns de `calibration/stereo_calibration.py` e `calibration/chessboard.py`, mantendo diferencas de fluxo e parametros quando necessario.

Observação: o comportamento específico foi preservado em cada contexto (por exemplo, saída JPG no fluxo do `tennisclub` e PNG no `z-shelf`).

## Comandos úteis

Exemplos de execução (a partir da raiz do workspace):

```bash
# Gerar tabuleiro de calibracao
python calibration/gerar_tabuleiro.py --help

# Calibracao mono
python calibration/calibrar_camera.py --help

# Visualizar distorcao
python calibration/visualizar_distorcao.py --help

# Sincronização por áudio
python tennisclub/src/sync/audio_sync/sincronizar_audio.py --help

# Rastreamento de bola
python tennisclub/src/tracking/rastrear_bola.py --help
```

Observação: os argumentos exatos variam por script. Use sempre `--help` antes da execução real.

### `tennisclub/`
Módulo principal do pipeline de captura, sincronia e análise de jogadas.

#### `tennisclub/src/audio/`
- `extrair_audio.py`: extrai trechos de áudio de vídeos (via ffmpeg) para análises de sincronia.

#### `tennisclub/src/sync/audio_sync/`
- `sincronizar_audio.py`: sincroniza dois vídeos pela correlação de áudio; pode corrigir drift e aplicar retificação estéreo.
- `analisar_drift_audio.py`: mede o drift de áudio ao longo do tempo e gera diagnóstico.

#### `tennisclub/src/sync/video_sync/`
- `sincronizar_metadata.py`: sincroniza pelo relógio/timestamp da metadata.
- `sincronizar_metadata_preview.py`: versão rápida para testar parâmetros de ajuste.
- `sincronizar_flash.py`: sincronização automática usando evento de flash.
- `analisar_drift_timestamps.py`: analisa divergência temporal absoluta entre câmeras.
- `calcular_parametros_manual.py`: calcula ajuste e drift a partir de referências visuais.
- `ferramenta_ajuste_fino.py`: busca ajuste fino de drift/sincronia.
- `gerar_clip_teste.py`: gera clipe curto para validação.
- `gerar_frames_sync.py`: gera frames lado a lado já com ajuste/drift.
- `gerar_video_final.py`: renderiza vídeo final sincronizado.
- `verificar_contagem_frames.py`: verifica divergência de contagem de frames ao longo do tempo.

#### `tennisclub/src/tracking/`
- `rastrear_bola.py`: rastreamento 2D da bola em vídeo.
- `seg_bola_sem_stereo.py`: segmentação de bola em modo mono (imagem única/lote).
- `calcular_velocidade_stereo.py`: estima velocidade 3D da bola com par estéreo.
- `calcular_rpm.py`: estimativa de rotação (RPM) da bola.

#### `tennisclub/src/utils/`
Conjunto de ferramentas auxiliares para validação e engenharia do pipeline.

- Qualidade e diagnóstico: `analisar_nitidez.py`, `verificar_gpu.py`, `verificar_sincronia.py`, `verificar_sinal.py`, `verificar_metadata.py`.
- Correção/inspeção de lente: `corrigir_distorcao_video.py`, `comparar_distorcao_video.py`, `comparar_distorcao_subtracao.py`, `ler_dados_calibracao.py`.
- Áudio e espectro: `calcular_atraso_cc.py`, `visualizar_espectograma.py`, `exportar_espectrograma_csv.py`.
- Apoio operacional: `extrair_amostra_frames.py`, `juntar_fotos_stereo.py`, `gerar_video_sync.py`, `sintonizar_hsv.py`, `sintonizar_forma.py`, `servidor_vr.py`, `exportar_para_quest.py`.

### `z-shelf/`
Área de estudos/protótipos para processamento 3D e comparação de abordagens (vídeo vs computação espacial).

- `src/calibrar_cameras.py`: calibração estéreo para o fluxo de experimentação, com reaproveitamento de helpers de `cv_tools/chessboard.py`.
- `src/preparar_calibracao_stereo.py`: wrapper CLI para o pipeline compartilhado de preparo em `cv_tools/stereo_prep.py`.
- `src/inspect_calibration.py`: inspeção de parâmetros de calibração salvos.
- `src/objetos_3d.py`: etapa de retificação/estrutura para análise de objetos 3D.
- `src/visualizar_nuvem.py`: visualização de nuvem de pontos com Open3D.

## Arquivos de apoio

- `tennisclub/docs/`: documentação técnica de calibração, configuração e sincronia.
- `tennisclub/calibracao_camera.npz` e `tennisclub/calibracao_stereo.npz`: parâmetros prontos de calibração.
- `tennisclub/pares_ruins.txt`: pares de imagens marcados como inadequados na calibração estéreo.

## Notas

- O repositório mistura scripts de produção (`tennisclub`) e área experimental (`z-shelf`).
- A calibracao foi centralizada em `calibration/`; scripts de projeto podem permanecer apenas como wrappers de fluxo.

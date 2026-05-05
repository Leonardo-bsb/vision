# Calibration

Documentacao do modulo independente de calibracao do workspace.

Esta pasta concentra o fluxo de calibracao mono e estereo, alem de utilitarios para gerar o padrao de tabuleiro e inspecionar a correcao de distorcao.

## Estrutura da pasta

- `calibrar_camera.py`: calibracao intrinseca de uma camera unica a partir de fotos de tabuleiro.
- `gerar_tabuleiro.py`: gera uma imagem do tabuleiro para impressao, com opcional de exportacao em PDF.
- `chessboard.py`: funcoes auxiliares para construcao dos pontos 3D do padrao e deteccao/refino de cantos.
- `stereo_prep.py`: preparo de pares sincronizados para calibracao estereo a partir de dois videos.
- `stereo_calibration.py`: calibracao estereo robusta com metricas de erro, retificacao e salvamento em `.npz`.
- `visualizar_distorcao.py`: comparacao entre imagem original e imagem corrigida por calibracao.
- `npz_files/`: armazenamento de arquivos de calibracao gerados.

## Dependencias

Minimo recomendado:

- Python 3.10+
- `opencv-python`
- `numpy`
- `scipy`
- `ffmpeg` no sistema para rotinas de audio/video em `stereo_prep.py`

Opcional:

- `Pillow` para exportar o tabuleiro tambem em PDF

## Fluxo recomendado

### 1. Gerar o tabuleiro

Use `gerar_tabuleiro.py` para criar o padrao de impressao.

```bash
python calibration/gerar_tabuleiro.py --rows 9 --cols 6 --lado-mm 50 --out calibration/tabuleiro_9x6.png
```

Observacoes:

- `rows` e `cols` sao cantos internos do tabuleiro.
- imprima em escala real, sem ajuste automatico da impressora.

### 2. Calibracao mono

Use `calibrar_camera.py` quando precisar obter intrinsecos e distorcao de uma unica camera.

```bash
python calibration/calibrar_camera.py pasta_com_fotos --rows 9 --cols 6 --size 5.0 --out calibration/npz_files/calibracao_camera.npz
```

Saida gerada:

- `camera_matrix`
- `dist_coeffs`
- `img_shape`
- `rms`
- `mean_error`

### 3. Preparar pares para calibracao estereo

Use `stereo_prep.py` para sincronizar dois videos pelo audio, corrigir drift opcionalmente e extrair pares L/R.

Esse modulo e pensado para ser importado por wrappers ou chamado a partir de scripts CLI do projeto. O fluxo principal e a funcao `preparar_calibracao_stereo(...)`.

Entradas principais:

- video esquerdo
- video direito
- pasta de saida
- intervalo entre frames
- correcao automatica de drift opcional

Saida:

- pares `frame_0000_L.*` e `frame_0000_R.*` prontos para calibracao estereo

### 4. Calibracao estereo

Use `stereo_calibration.py` para calcular intrinsecos, extrinsecos e retificacao do par de cameras.

O fluxo principal e a funcao `calibrar_stereo_robusta(...)`.

Parametros principais:

- `dir_fotos`: pasta com pares L/R
- `rows`, `cols`: cantos internos do tabuleiro
- `square_size`: tamanho fisico do quadrado
- `output_file`: arquivo `.npz` de saida

Saida gerada no `.npz`:

- `mtx_l`, `dist_l`
- `mtx_r`, `dist_r`
- `R`, `T`
- `R1`, `R2`, `P1`, `P2`, `Q`

Metricas reportadas:

- RMS mono esquerdo
- RMS mono direito
- RMS estereo
- numero de pares detectados
- pares com falha de deteccao

### 5. Visualizar correcao de distorcao

Use `visualizar_distorcao.py` para conferir rapidamente se a calibracao faz sentido visualmente.

```bash
python calibration/visualizar_distorcao.py imagem.jpg calibration/npz_files/calibracao_camera.npz --out comparacao.jpg
```

Esse script aceita tanto arquivos mono quanto arquivos estereo. Em calibracao estereo, ele usa a camera esquerda por padrao.

## Convencoes esperadas

### Nome dos pares estereo

O calibrador estereo tenta inferir o par direito a partir do esquerdo. Os formatos esperados incluem:

- `*_L.jpg` / `*_R.jpg`
- `*_L.png` / `*_R.png`
- `L_*.jpg` / `R_*.jpg`
- `xxx-L.jpg` / `xxx-R.jpg`

### Unidade fisica

O valor de `square_size` define a unidade do baseline estimado:

- se usar `5.0`, o baseline sai em centimetros
- se usar `0.024`, o baseline sai em metros

Escolha uma unidade consistente com o restante do pipeline.

## Boas praticas de captura

Para reduzir erro de reprojecao e melhorar a retificacao:

- desligue estabilizacao digital
- use a mesma resolucao da captura final
- mantenha foco fixo quando possivel
- prefira shutter rapido para evitar motion blur
- mantenha ISO baixo e luz forte
- evite diferencas de exposicao e cor entre as duas cameras
- nao troque modo de lente/FOV entre calibracao e captura real

## Observacoes

- A calibracao agora e independente de `tennisclub` e `z-shelf`.
- Scripts de projeto podem consumir este modulo, mas a implementacao canonica esta em `calibration/`.
- Se houver wrappers externos, eles devem apenas chamar estas funcoes centrais.
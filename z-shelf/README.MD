# Análise de Tecnologias: ARCore vs Processamento de Vídeo (Depth Anything)

## O Diferencial do ARCore (Computação Espacial)

Mudar para **ARCore** (ou ARKit no iOS) eleva o nível do projeto de "Processamento de Imagem" para **Computação Espacial**.

### Vantagens sobre o método atual (Vídeo + IA)

1.  **Escala Real (Métrica):**
    *   **Atual (Vídeo/Depth Anything):** O algoritmo "chuta" a profundidade relativa. Ele sabe que o objeto está na frente, mas não sabe as dimensões reais (cm/m).
    *   **ARCore:** Entende o mundo em metros. Permite perguntas como: "Se este espaço vazio tem 15cm e o produto tem 10cm, cabe mais um?". Crucial para Planogramas e varejo.

2.  **Fusão de Sensores (Robustez):**
    *   **Atual:** Falha em objetos lisos (como garrafas de amaciante) por falta de textura para rastreamento visual.
    *   **ARCore:** Usa **acelerômetro e giroscópio** do celular em conjunto com a câmera. Mesmo apontando para uma parede branca, ele detecta o movimento físico.

3.  **Nuvem de Pontos (Point Cloud):**
    *   Em vez de separar pixels 2D, o ARCore gera uma nuvem de pontos 3D. Separar objetos em 3D é mais fácil (verificar espaços vazios entre aglomerados de pontos) do que tentar adivinhar bordas em imagens com cores similares.

## Limitações Técnicas

### O Problema do Vídeo Pré-gravado
O **Google ARCore** não pode ser aplicado em vídeos MP4 antigos gravados apenas com a câmera.
*   **Motivo:** O ARCore depende de dados inerciais (aceleração e rotação física do dispositivo) sincronizados com a imagem. Um arquivo de vídeo comum perde esses dados.
*   **Consequência:** Para usar ARCore, a captura deve ser feita via aplicativo específico que processe os sensores em tempo real.

## Novo Fluxo de Trabalho Sugerido

Para adotar essa tecnologia, a arquitetura do projeto deve ser dividida em duas partes:

1.  **Captura (Cliente Mobile):**
    *   Utilizar aplicativos de Escaneamento 3D (ex: **Polycam**, **Scaniverse**, **Mage**) ou desenvolver um app Android nativo com ARCore.
    *   **Saída Recomendada:** Nuvem de Pontos **`.ply`** (Polygon File Format).
    *   *Nota:* Evite malhas (`.obj`) para análise, pois elas tendem a fundir objetos próximos, dificultando a contagem.

2.  **Processamento (Servidor Python/WSL):**
    *   Recebe o arquivo 3D.
    *   Utiliza bibliotecas como **Open3D**.
    *   Aplica algoritmos de clusterização 3D (ex: **DBSCAN**) para contar e segmentar os produtos baseando-se na densidade dos pontos, não na cor.

## Sobre a Biblioteca Open3D

A **Open3D** é a ferramenta fundamental para a etapa de processamento neste projeto. Ela é uma biblioteca open-source moderna que permite:
1.  **Leitura Eficiente:** Carrega instantaneamente arquivos de nuvem de pontos (`.ply`) gerados por scanners móveis.
2.  **Visualização Interativa:** Oferece janelas de visualização para inspecionar a geometria da prateleira em 3D.
3.  **Algoritmos Prontos:** Implementa funções complexas como **DBSCAN** (para separar objetos próximos) e **Remoção de Outliers** (limpeza de ruído) com alta performance em Python.
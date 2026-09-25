# Guia: gerar plantas no ArcGIS Pro (analistas)

Este guia é para quem precisa gerar a **planta do núcleo**, a **planta de loteamento** ou a **planta de vértices/confrontantes/memorial** sem usar VPN nem banco SDE.

## O que você precisa

- ArcGIS Pro instalado
- Conta no portal ITERMA (mesmo acesso do mapa REURB)
- Pasta do pacote Desktop com as toolboxes e o GDB auxiliar já preparado pelo TI
- Um número de REURB coletivo válido (exemplo: `051201571/2026`)

## Passo a passo

### 1. Entrar no portal

1. Abra o ArcGIS Pro.
2. Faça login no portal ITERMA (o FeatureServer exige autenticação).
3. Sem login, a ferramenta não consegue ler Bairro, Quadras e Lotes.

### 2. Abrir o projeto

1. Abra `pacote_desktop/REURB_Plantas_Desktop.aprx` (se o TI já criou), **ou**
2. Em Catalog → Toolboxes → Add Toolbox e selecione `REURB_Plantas.pyt`
   (caixa única com as cinco ferramentas Desktop).

### 3. Conferir o processo no mapa (recomendado)

1. Na camada **Bairro**, filtre ou busque pelo campo `n_coletivo`.
2. Confira:
   - `status` igual a **2** ou **4** (pré-vetorização ou vetorização concluída)
   - `responsavel_tecnico` preenchido

Se o status estiver em andamento, a ferramenta vai parar de propósito.

### 4. Rodar a ferramenta Desktop

1. Abra Geoprocessing.
2. Escolha uma das ferramentas:
   - **Gerar Planta Núcleo (Desktop)** — planta + memorial de vértices
   - **Gerar Planta Loteamento (Desktop)** — planta + anexo de lotes
   - **Gerar Planta Vértices Confrontantes Memorial (Desktop)** — planta + memorial narrativo + quadro de coordenadas (UTM, com confrontantes)
   - **Gerar Memoriais de Quadras (Desktop)** — um PDF A4 por quadra
   - **Gerar Planta Lote Institucional (Desktop)** — planta + memorial + quadro de um lote institucional (Municipal ou Estadual)
3. Preencha:
   - **Número do REURB coletivo**
   - **Pasta de saída** (onde salvar PDF, CSV e ZIP)
   - Na ferramenta de memorial ou institucional, escolha também a **Densidade de vértices**: `integral` (padrão) ou `simplificado`
   - Na **Institucional**, informe também **Quadra** e **Lote**
4. Deixe a URL do FeatureServer como está (só mude se o TI pedir).
5. Os campos de formação/CREA são opcionais: use só se o cadastro local do RT estiver desatualizado.
6. Clique em Run.

### 5. Pegar o resultado

A ferramenta cria uma **subpasta** dentro da pasta que você escolheu
(nome com ferramenta, número do processo, data e pid). Lá entram o PDF,
o ZIP e o `diario.json`. Se um arquivo com o mesmo nome já existir, a
corrida para em vez de sobrescrever.

| Arquivo | Conteúdo |
|---------|----------|
| `diario.json` | Versão do pacote, ArcGIS Pro, scratch e contagens (núcleo/loteamento) |
| `planta_nucleo_XXXX.pdf` ou `planta_loteamento_XXXX.pdf` | Planta em PDF (Núcleo/Loteamento) |
| `planta_vertices_memorial_XXXX.pdf` | Planta + memorial narrativo + quadro (ferramenta de memorial) |
| `planta_institucional_XXXX_Q*_L*.pdf` | Planta + memorial + quadro (lote institucional) |
| `quadro_coordenadas_XXXX.csv` | CSV do quadro de coordenadas (ferramenta de memorial) |
| `quadro_institucional_XXXX_Q*_L*.csv` | CSV do quadro (institucional) |
| `shape_XXXX.zip` ou `shape_vertices_XXXX.zip` | Shapefile do bairro/vértices |
| `shape_institucional_XXXX_Q*_L*.zip` | Shapefile do lote institucional |

A mensagem final da ferramenta mostra os caminhos. Na ferramenta de
memorial, se os layouts ainda não tiverem sido criados pelo TI no Pro, o
CSV e o ZIP são salvos normalmente e a mensagem final explica que o PDF
está pendente.

## Diferença entre as três plantas

| | Núcleo | Loteamento | Vértices/Confrontantes/Memorial |
|---|--------|------------|------|
| Foco | Perímetro e memorial | Urbanização e beneficiários | Perímetro cartorial (UTM) |
| Anexo | Tabela de vértices | Lista de lotes | Memorial narrativo + quadro de coordenadas |
| Confrontantes | Sim | Não | Sim |
| Coordenadas | Geográficas | Geográficas | UTM do fuso do processo |
| Densidade de vértices | Fixa | Fixa | `integral` ou `simplificado` (parâmetro) |

## Quando pedir ajuda

- **Dados**: status errado, RT vazio, REURB inexistente → equipe de edição/vetorização
- **Ferramenta / GDB auxiliar / login**: → TI / suporte GIS

Veja também: [checklist-erros.md](checklist-erros.md)

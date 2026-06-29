# Gerar Prancha Loteamento

Ferramenta separada para gerar a **PRANCHA 02 - PLANTA DO LOTEAMENTO** com base em shapefile de lotes e, quando informado, shapefile do bairro/perimetro.

## Caminho da ferramenta no ArcGIS Pro

Adicione a toolbox:

```text
C:\REURB\ferramentas\gerarpranchaloteamento\GerarPranchaLoteamento.pyt
```

Ferramenta:

```text
GerarPranchaLoteamentoTool
```

## Estrutura da pasta

```text
C:\REURB\ferramentas\gerarpranchaloteamento
  GerarPranchaLoteamento.pyt
  gerar_prancha_loteamento_arcgis.py
  gerar_prancha_loteamento.py
  caminhos_gerais.py
  inputs\
  layout\
  resultados\
  tmp\
```

## Fluxo esperado

1. Informar o `inputJson` na ferramenta do ArcGIS Pro.
2. A ferramenta carrega o shapefile de lotes como planta principal.
3. A ferramenta carrega o shapefile do bairro ao fundo, quando `shpBairro` for informado.
4. Area e perimetro do quadro da prancha saem do `shpBairro`.
5. A lista de beneficiarios usa os lotes com `status` 1 e 4.
6. Os resultados saem em subpasta dentro de `resultados`.

## Usar Camadas Atuais do ArcGIS Pro

Para usar as camadas vivas do projeto `REURB_ITERMA.aprx`, informe:

```json
"exportarCamadasArcGIS": true
```

Quando ligado, o fluxo exporta automaticamente `Bairro`, `Lotes`, `Eixo Viario` e `marcacao_frente_lote_ma_reurb` para SHP filtrado por processo/bairro antes de gerar a prancha.

Projeto padrao:

```text
C:\Users\gusta\OneDrive\Documentos\ArcGIS\Projects\REURB_ITERMA\REURB_ITERMA.aprx
```

## Nova prancha - Planta Geral de Quadras

Para gerar a planta geral com quadro de quadras, informe:

```json
{"tipoPrancha":"plantaGeralQuadras","shpLotes":"C:\\REURB\\SHP\\lotes_050601273_2026.shp","shpBairro":"C:\\REURB\\SHP\\bairro_centro_052601273_2026.shp","dados":{"numeroProcessoColetivo":"050601273/2026","municipio":"Peri Mirim","bairro":"Centro"},"responsavelTecnico":"leandro_miranda_da_silva"}
```

Saida esperada:

```text
PRANCHA_03-_PLANTA_GERAL_DE_QUADRAS_<MUNICIPIO>_<BAIRRO>_ARCGIS.pdf
```

O quadro da prancha lista:

- Quadra
- Area total da quadra em m2, calculada pela soma das geometrias dos lotes da quadra em SIRGAS 2000 / UTM 23S
- Quantidade de lotes por quadra

## Planta Geral Municipal do REURB

Para gerar uma planta unica do resultado do REURB para todo o municipio, use:

```json
{"tipoPrancha":"plantaGeralMunicipio","dados":{"municipio":"Peri Mirim"},"eixoViario":"C:\\REURB\\SHP\\eixo_viario_Peri Mirim.shp","responsavelTecnico":"leandro_miranda_da_silva","gerarMemorial":true}
```

Quando `shpLotesLista` e `shpBairrosLista` nao forem informados, a ferramenta busca automaticamente:

- `C:\REURB\SHP\lotes_*.shp`
- `C:\REURB\SHP\bairro_*.shp`

Saidas esperadas em `resultados\peri_mirim_reurb_geral`:

- `PRANCHA_01-_PLANTA_GERAL_REURB_PERI_MIRIM_ARCGIS.pdf`
- `MEMORIAL_GERAL_REURB_PERI_MIRIM.pdf`
- `MEMORIAL_GERAL_REURB_PERI_MIRIM.json`

## Campos esperados no shapefile de lotes

- `status`
- `nome`
- `cpf_cnpj_`
- campo de quadra/lote, quando existir, para rotulo do lote

## Legenda de status

```text
1 - Concluida no ponto fixo
2 - Em andamento
3 - Aguardando inicio
4 - Concluida em campo
5 - Litigio
6 - Pendente de confirmacao
7 - Area Rural
8 - Cancelado
9 - Terreno
10 - Faixa de Dominio
11 - Alagado
```

## Exemplo - Centro

```json
{"shpLotes":"C:\\REURB\\SHP\\lotes_050601273_2026.shp","shpBairro":"C:\\REURB\\SHP\\bairro_centro_052601273_2026.shp","dados":{"numeroProcessoColetivo":"050601273/2026","municipio":"Peri Mirim","bairro":"Centro"},"anexarLista":true}
```

## Exemplo - Campo de Pouso

```json
{"shpLotes":"C:\\REURB\\SHP\\lotes_051201571_2026.shp","shpBairro":"C:\\REURB\\SHP\\bairro_campodepouso_051201571_2026.shp","dados":{"numeroProcessoColetivo":"051201571/2026","municipio":"Peri Mirim","bairro":"Campo de Pouso"},"anexarLista":true}
```

## Observacoes de teste

- Execute pelo ArcGIS Pro para usar o layout georreferenciado.
- Caso a lista de beneficiarios nao seja anexada por falta de `reportlab` no Python do ArcGIS, a ferramenta tenta usar o Python auxiliar do Codex.
- O arquivo `gerar_prancha_loteamento.py` fica preservado como gerador auxiliar direto por shapefile, sem depender do ArcGIS layout.

# Gerar Planta Geral por Bairro

Ferramenta ArcGIS Pro separada para gerar a planta geral de um bairro/nucleo do REURB, com:

- mapa geral das quadras;
- lotes ao fundo;
- limite do bairro com vertices numerados;
- frente de cada lote em magenta;
- legenda identificando limite do bairro, vertices, lotes, quadras e frente de lote;
- quadro com quadra, area e quantidade de lotes;
- planta de situacao;
- carimbo institucional.
- memorial do eixo/limite do bairro em PDF.

## Caminho da toolbox

```text
C:\REURB\ferramentas\gerarplantageralbairro\GerarPlantaGeralBairro.pyt
```

Ferramenta:

```text
GerarPlantaGeralBairroTool
```

## Memoriais descritivos por quadra

Toolbox separada para gerar um PDF de memorial descritivo para cada quadra do bairro, sempre exportando as camadas atuais do ArcGIS Pro antes do processamento:

```text
C:\REURB\ferramentas\gerarplantageralbairro\GerarMemoriaisQuadrasBairro.pyt
```

Ferramenta:

```text
GerarMemoriaisQuadrasBairroTool
```

Use o mesmo JSON do modo `exportarCamadasArcGIS`, com a camada `quadras` informada em `camadasArcGIS`. A saida padrao fica em:

```text
C:\REURB\ferramentas\gerarplantageralbairro\resultados\memoriais_quadras\<municipio>\<bairro>\<processo>
```

A ferramenta gera:

- um PDF individual por quadra em `pdfs`;
- um JSON tecnico por quadra em `dados_json`;
- um PDF consolidado do bairro com todos os memoriais.

Quando a ferramenta for rodada dentro do ArcGIS Pro, pode usar:

```json
"aprxCamadas": "CURRENT"
```

Assim ela usa diretamente o projeto aberto e as camadas visiveis/atuais da sessao.

## Exemplo de jsonInput

```json
{"shpLotes":"C:\\REURB\\SHP\\lotes_050601273_2026.shp","shpBairro":"C:\\REURB\\SHP\\bairro_centro_052601273_2026.shp","shpFrenteLotes":"C:\\REURB\\ferramentas\\gerarplantageralbairro\\marcacoes\\marcacao_frente_lote_ma_reurb.shp","eixoViario":"C:\\REURB\\SHP\\eixo_viario_Peri Mirim.shp","dados":{"numeroProcessoColetivo":"050601273/2026","municipio":"Peri Mirim","bairro":"Centro"},"responsavelTecnico":"leandro_miranda_da_silva","gerarMemorial":true}
```

## Exemplo com camadas atuais do ArcGIS Pro

Use `exportarCamadasArcGIS` para a ferramenta abrir o APRX, exportar as camadas atuais filtradas por `n_coletivo` e gerar a planta com os dados mais recentes do FeatureServer.

```json
{
  "exportarCamadasArcGIS": true,
  "aprxCamadas": "C:\\Users\\gusta\\OneDrive\\Documentos\\ArcGIS\\Projects\\REURB_ITERMA\\REURB_ITERMA.aprx",
  "camadasArcGIS": {
    "lotes": "Lotes",
    "bairro": "Bairro",
    "eixoViario": "Eixo Viario"
  },
  "shpFrenteLotes": "C:\\REURB\\ferramentas\\gerarplantageralbairro\\marcacoes\\marcacao_frente_lote_ma_reurb.shp",
  "dados": {
    "numeroProcessoColetivo": "050601273/2026",
    "municipio": "Peri Mirim",
    "bairro": "Centro"
  },
  "responsavelTecnico": "leandro_miranda_da_silva",
  "gerarMemorial": true
}
```

Nesse modo, a ferramenta exporta:

- `lotes.shp` filtrado por `n_coletivo`;
- `bairro.shp` filtrado por `n_coletivo` e/ou nome do bairro;
- `eixo_viario.shp` filtrado por intersecao com o limite do bairro.

Os SHPs exportados ficam em uma subpasta de trabalho dentro de `resultados`.

Os resultados saem por padrao em:

```text
C:\REURB\ferramentas\gerarplantageralbairro\resultados\<bairro>
```

## Marcacao manual da frente de lote

A ferramenta aceita `shpFrenteLotes`, um shapefile unico de pontos marcado manualmente no ArcGIS.

SHP padrao estadual:

```text
C:\REURB\ferramentas\gerarplantageralbairro\marcacoes\marcacao_frente_lote_ma_reurb.shp
```

Campos padronizados:

- `quadra`
- `lote`
- `n_coletivo`
- `municipio`
- `bairro`
- `obs`

Fluxo:

1. Adicione o SHP de pontos da pasta `marcacoes` no ArcGIS.
2. Marque um ponto proximo da frente de cada lote.
3. Salve as edicoes.
4. Rode a ferramenta com o JSON correspondente.

Quando `shpFrenteLotes` tiver pontos com `quadra`, `lote` e `n_coletivo`, a ferramenta usa esses atributos para identificar o lote e escolher o segmento mais proximo do ponto. Quando nao houver atributos preenchidos, usa a proximidade espacial. Quando nao houver ponto para um lote, a ferramenta usa o eixo viario informado; se ainda assim nao encontrar eixo proximo, usa o maior segmento do lote como fallback.

Os pontos de marcacao nao aparecem na planta final; eles servem apenas como apoio tecnico para definir a linha de frente do lote.

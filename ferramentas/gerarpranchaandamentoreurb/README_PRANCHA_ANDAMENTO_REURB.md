# Gerar Prancha Andamento REURB

Ferramenta separada para gerar o resultado **Prancha Andamento REURB** na etapa de **Pre-vetorizacao**, usando as camadas atuais do ArcGIS Pro.

## Caminho da ferramenta no ArcGIS Pro

Adicione a toolbox:

```text
C:\REURB\ferramentas\gerarpranchaandamentoreurb\GerarPranchaAndamentoREURB.pyt
```

Ferramenta:

```text
GerarPranchaAndamentoREURBTool
```

## Entrada inicial

Para gerar os tres primeiros resultados do print, informe como `inputJson` o caminho:

```text
C:\REURB\ferramentas\gerarpranchaandamentoreurb\inputs\prancha_andamento_reurb_primeiros.json
```

Coletivos configurados:

- Vila Socorro: `051301592/2026`
- Centro: `051301595/2026`
- Setor Maciel: `051301596/2026`

## Saidas dos PDFs

Os PDFs e a copia do APRX da prancha ficam em:

```text
C:\REURB\ferramentas\gerarpranchaandamentoreurb\resultados\<bairro>_<n_coletivo>
```

O PDF final tambem e copiado com nome:

```text
PRANCHA_ANDAMENTO_REURB_<MUNICIPIO>_<BAIRRO>_<N_COLETIVO>_ARCGIS.pdf
```

## Camadas exportadas

Os SHPs filtrados das camadas atuais do ArcGIS ficam dentro do mesmo diretorio `resultados`, organizados por municipio, bairro e numero:

```text
C:\REURB\ferramentas\gerarpranchaandamentoreurb\resultados\<municipio>\<bairro>\<n_coletivo>
```

## Camadas usadas

Por padrao a ferramenta abre:

```text
C:\Users\gusta\OneDrive\Documentos\ArcGIS\Projects\REURB_ITERMA\REURB_ITERMA.aprx
```

E exporta as camadas:

- `Bairro`
- `Lotes`
- `Quadras`
- `Eixo Viario`

O filtro principal e `n_coletivo`.

# Automacao REURB - Gerar Planta Nucleo

Este documento orienta o uso da ferramenta `GerarPlantaNucleoTool` no ArcGIS Pro para gerar os pacotes de planta, quadro de coordenadas e memorial descritivo.

## 1. InputJson

Cole o JSON no parametro `inputJson` da ferramenta.

Modelo:

```json
{"dados":{"numeroProcessoColetivo":"NUMERO/ANO","bairro":"NOME DO BAIRRO","matricula":""},"responsavelTecnico":"id_do_responsavel","forcarGeracao":true}
```

Campo de Pouso:

```json
{"dados":{"numeroProcessoColetivo":"051201571/2026","bairro":"CAMPO DE POUSO","matricula":""},"responsavelTecnico":"bruna_silva_sa_pereira","forcarGeracao":true}
```

Centro:

```json
{"dados":{"numeroProcessoColetivo":"050601273/2026","bairro":"Centro","matricula":""},"responsavelTecnico":"leandro_miranda_da_silva","forcarGeracao":true}
```

## 2. Como gerar outro bairro

1. Confirme que o perimetro existe na camada de bairro com o campo `n_coletivo`.
2. Confirme o numero do processo coletivo exatamente como esta no dado, por exemplo `051201571/2026`.
3. Informe o nome do bairro no JSON.
4. Escolha o responsavel tecnico pelo ID cadastrado em `responsaveis_tecnicos.txt`.
5. Rode a ferramenta no ArcGIS Pro.

Exemplo para outro bairro:

```json
{"dados":{"numeroProcessoColetivo":"000000000/2026","bairro":"NOME DO BAIRRO","matricula":""},"responsavelTecnico":"leandro_miranda_da_silva","forcarGeracao":true}
```

O municipio e calculado automaticamente pela intersecao do perimetro com a camada de municipios.

## 3. Resultados gerados

Os arquivos saem em:

```text
C:\REURB\ferramentas\gerarplantanucleo\resultados\<bairro>_<processo>
```

Principais arquivos:

```text
planta_simplificada_com_quadro_<processo>.pdf
planta_vertices_memorial_com_memorial_<processo>.pdf
memorial_descritivo_<processo>.pdf
quadro_coordenadas_<processo>.pdf
quadro_coordenadas_<processo>.csv
quadro_coordenadas_<processo>.html
quadro_vertices_prancha_completo_<processo>.png
resultado_<processo>.json
shape_<processo>.zip
```

## 4. Entendimento do fluxo

### Planta simplificada

Arquivo:

```text
planta_simplificada_com_quadro_<processo>.pdf
```

Uso:

- planta grafica limpa;
- vertices reduzidos para legibilidade;
- anexada ao quadro de coordenadas da planta simplificada;
- usa `dadosPerimetroPlantaSimplificada` no JSON.

### Planta de vertices do memorial

Arquivo:

```text
planta_vertices_memorial_com_memorial_<processo>.pdf
```

Uso:

- planta de conferencia;
- usa a sequencia integral dos vertices do memorial;
- anexada ao memorial descritivo;
- usa `dadosPerimetro` no JSON.

### Memorial descritivo

Arquivo:

```text
memorial_descritivo_<processo>.pdf
```

Uso:

- documento analitico oficial;
- descreve a sequencia completa de vertices, coordenadas, azimutes, distancias e confrontantes.

## 5. Campos importantes no JSON de saida

```text
dadosPerimetro
```

Vertices completos usados no memorial descritivo.

```text
dadosPerimetroPlantaSimplificada
```

Vertices reduzidos usados na planta simplificada.

```text
fluxoDocumentos.plantaSimplificada
```

Explica o pacote da planta simplificada com quadro.

```text
fluxoDocumentos.plantaVerticesMemorial
```

Explica o pacote da planta com vertices integrais e memorial.

## 6. Responsaveis tecnicos

Os responsaveis ficam em:

```text
C:\REURB\ferramentas\gerarplantanucleo\responsaveis_tecnicos.txt
```

Para adicionar outro tecnico, crie uma nova chave:

```ini
[nome_sobrenome]
nome=Nome Completo
email=email@exemplo.com
formacao=Engenheiro Civil
registro=CREA: 0000000000
```

No `inputJson`, use:

```json
"responsavelTecnico":"nome_sobrenome"
```

## 7. Camadas e caminhos esperados

### Bairro

A ferramenta tenta usar, nesta ordem:

1. FeatureServer do ITERMA:

```text
https://www.arcgis.iterma.ma.gov.br/server/rest/services/CAMADAS_ITERMA/REURB_ITERMA/FeatureServer/8
```

2. Shapefiles locais em:

```text
C:\REURB\SHP
```

O shapefile de bairro precisa ter o campo:

```text
n_coletivo
```

### Eixo viario

A ferramenta tenta usar, nesta ordem:

1. FeatureServer do ITERMA:

```text
https://www.arcgis.iterma.ma.gov.br/server/rest/services/CAMADAS_ITERMA/REURB_ITERMA/FeatureServer/0
```

2. Shapefile local de fallback:

```text
C:\REURB\SHP\eixo_viario_Peri Mirim.shp
```

O eixo precisa ter o campo:

```text
logradouro
```

Para outro municipio, a ferramenta prioriza o FeatureServer. Se for trabalhar offline,
exporte o eixo viario correspondente e ajuste o caminho em `confrontacao_eixo_viario.py`,
constante `EIXO_VIARIO_LOCAL`.

### Logos do memorial

Hoje o memorial procura:

```text
C:\Users\gusta\Downloads\Brasão_do_Maranhão.png
C:\Users\gusta\Downloads\Logo_do_governo_do_Maranhão_(2023-2027).png
```

Em outra maquina, coloque as imagens no mesmo caminho do usuario ou ajuste os caminhos em `gerar_memorial_descritivo.py`.

## 8. Como compartilhar com outro tecnico

Procedimento recomendado:

1. Copiar a pasta inteira:

```text
C:\REURB\ferramentas\gerarplantanucleo
```

2. Copiar ou recriar a pasta de dados:

```text
C:\REURB\SHP
```

3. Garantir que existam:

```text
C:\REURB\SHP\bairro*.shp
C:\REURB\SHP\eixo_viario_<municipio>.shp
```

4. Garantir acesso ao ArcGIS Pro com licencas necessarias de geoprocessamento.
5. Abrir o ArcGIS Pro.
6. Adicionar a toolbox:

```text
C:\REURB\ferramentas\gerarplantanucleo\GerarPlantaNucleo.pyt
```

7. Executar `GerarPlantaNucleoTool`.
8. Informar o `inputJson`.

## 9. Observacoes operacionais

- Use `forcarGeracao:true` quando estiver testando localmente e quiser gerar mesmo se o status nao estiver pronto.
- Para entrega formal, confira se o status do bairro esta adequado.
- A area e o perimetro impressos nas pranchas correspondem ao perimetro real/completo.
- A planta simplificada e apenas uma representacao grafica para legibilidade.
- O memorial descritivo e a referencia analitica completa.
- Guarde a pasta `resultados/<bairro>_<processo>` inteira como pacote de entrega.

## 10. Checklist antes de entregar

- Conferir se o responsavel tecnico esta correto.
- Conferir bairro, municipio, area e perimetro.
- Conferir se a planta simplificada tem o quadro anexado.
- Conferir se a planta de vertices do memorial tem o memorial anexado.
- Conferir se o memorial possui assinatura na mesma pagina.
- Conferir se o quadro de coordenadas esta com 4 casas decimais.
- Conferir se os confrontantes principais foram preenchidos.

## 11. Prancha 02 - Planta do Loteamento no ArcGIS

A ferramenta `GerarPranchaLoteamento.pyt` gera a `PRANCHA_02-_PLANTA_DO_LOTEAMENTO_MUNICIPIO_BAIRRO` usando o layout do ArcGIS Pro.

Ela copia o `project_layout.aprx`, monta a planta no `MAP_FRAME`, cria uma camada de lotes por `status`, aplica cores de legenda, rotula os lotes como `Qxx-Lxx`, exporta a planta em PDF e tenta anexar a Lista de Beneficiarios com os lotes de status `1` e `4`.

Exemplo para Campo de Pouso:

```json
{"shpLotes":"C:\\REURB\\SHP\\lotes_051201571_2026.shp","shpBairro":"C:\\REURB\\SHP\\bairro_campodepouso_051201571_2026.shp","dados":{"numeroProcessoColetivo":"051201571/2026","municipio":"Peri Mirim","bairro":"Campo de Pouso"},"anexarLista":true}
```

Exemplo para Centro:

```json
{"shpLotes":"C:\\REURB\\SHP\\lotes_050601273_2026.shp","shpBairro":"C:\\REURB\\SHP\\bairro_centro_052601273_2026.shp","dados":{"numeroProcessoColetivo":"050601273/2026","municipio":"Peri Mirim","bairro":"Centro"},"anexarLista":true}
```

Saida esperada:

```text
resultados\<bairro>_<processo>\PRANCHA_02-_PLANTA_DO_LOTEAMENTO_<MUNICIPIO>_<BAIRRO>_ARCGIS.pdf
```

## 12. Sincronizar entregas no Google Drive

Apos gerar os resultados, sincronize com a pasta de entregas no Drive:

```powershell
cd C:\REURB\ferramentas\gerarplantanucleo
python sincronizar_entregas_drive.py --todos
```

O script separa automaticamente arquivos de entrega (`03_ENTREGAS`) e internos (`04_INTERNO`).

Documentacao no Drive do cliente: `00_DOCS\INSTRUCOES.txt`
Documentacao interna: `README_SINCRONIZAR_ENTREGAS.md`

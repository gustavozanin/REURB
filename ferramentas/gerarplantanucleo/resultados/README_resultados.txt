Organizacao dos resultados
==========================

Os resultados finais ficam separados por bairro e processo:

- campo_de_pouso_051201571_2026
  - Processo REURB coletivo: 051201571/2026
  - Bairro: CAMPO DE POUSO
  - Responsavel tecnico padrao: bruna_silva_sa_pereira
  - inputJson:
    {"dados":{"numeroProcessoColetivo":"051201571/2026","bairro":"CAMPO DE POUSO","matricula":""},"responsavelTecnico":"bruna_silva_sa_pereira","forcarGeracao":true}

- centro_050601273_2026
  - Processo REURB coletivo: 050601273/2026
  - Bairro: Centro
  - Responsavel tecnico padrao: leandro_miranda_da_silva
  - inputJson:
    {"dados":{"numeroProcessoColetivo":"050601273/2026","bairro":"Centro","matricula":""},"responsavelTecnico":"leandro_miranda_da_silva","forcarGeracao":true}

Padrao de arquivos por pasta:

- planta_simplificada_com_quadro_<processo>.pdf
- planta_vertices_memorial_com_memorial_<processo>.pdf
- memorial_descritivo_<processo>.pdf
- quadro_coordenadas_<processo>.pdf
- quadro_coordenadas_<processo>.csv
- quadro_coordenadas_<processo>.html
- quadro_vertices_prancha_completo_<processo>.png
- resultado_<processo>.json
- shape_<processo>.zip

Observacao:
A ferramenta GerarPlantaNucleoTool foi ajustada para salvar novas geracoes diretamente em resultados/<bairro>_<processo>.
Nas proximas geracoes pelo ArcGIS, a ferramenta produz duas plantas:

- planta_simplificada_com_quadro_<processo>.pdf: prancha grafica legivel, com vertices reduzidos, anexada ao Quadro de Coordenadas da Planta Simplificada.
- planta_vertices_memorial_com_memorial_<processo>.pdf: prancha de conferencia com a sequencia integral de vertices do Memorial Descritivo, anexada ao Memorial Descritivo.

A area e o perimetro impressos nas pranchas correspondem ao perimetro real/completo. A planta simplificada e uma representacao grafica para legibilidade e nao deve ser usada isoladamente para recalculo de area.

No JSON de saida:

- dadosPerimetro: vertices completos usados no Memorial Descritivo.
- dadosPerimetroPlantaSimplificada: vertices reduzidos usados na planta simplificada.
- fluxoDocumentos.plantaSimplificada: descreve o pacote planta simplificada + quadro.
- fluxoDocumentos.plantaVerticesMemorial: descreve o pacote planta vertices do memorial + memorial descritivo.

# Sincronizar entregas com o Google Drive

Este script copia os resultados gerados no computador para a pasta de entregas no Google Drive, separando automaticamente:

- **03_ENTREGAS** — arquivos que podem compor o ZIP formal
- **04_INTERNO** — JSON, CSV, duplicatas e intermediarios (nao enviar ao ITERMA)

## Pre-requisitos

1. Google Drive instalado e sincronizado no Windows
2. Pasta de entregas criada em:

```text
H:\Meu Drive\Entregas_ITERMA_REURB
```

3. Resultados gerados previamente pelo ArcGIS em:

```text
C:\REURB\ferramentas\gerarplantanucleo\resultados\<nucleo>_<processo>\
```

## Como executar

Abra o **Prompt de Comando** ou **PowerShell** e rode:

```powershell
cd C:\REURB\ferramentas\gerarplantanucleo
python sincronizar_entregas_drive.py --todos
```

Sincronizar apenas um nucleo:

```powershell
python sincronizar_entregas_drive.py --nucleo campo_de_pouso_051201571_2026
python sincronizar_entregas_drive.py --nucleo centro_050601273_2026
```

Simular sem copiar arquivos:

```powershell
python sincronizar_entregas_drive.py --todos --dry-run
```

Se o Drive estiver em outro caminho:

```powershell
python sincronizar_entregas_drive.py --todos --drive "D:\Google Drive\Entregas_ITERMA_REURB"
```

## O que o script faz

| Origem | Destino no Drive |
|---|---|
| `memorial_descritivo_<processo>.pdf` | `03_ENTREGAS/.../01_perimetro/` |
| `planta_vertices_*.pdf` | `03_ENTREGAS/.../01_perimetro/` |
| `quadro_areas_*.pdf` | `03_ENTREGAS/.../02_areas/` |
| `PRANCHA_02-_PLANTA_*` (ArcGIS) | `03_ENTREGAS/.../03_loteamento/` |
| `shape_*.zip` | `03_ENTREGAS/.../06_geodata/` |
| Memoriais de quadras | `03_ENTREGAS/.../04_quadras/` |
| Payloads, CSV, HTML, PNG, duplicatas | `04_INTERNO/.../` |

Apos cada execucao, o arquivo `STATUS_ENTREGA.txt` do nucleo e atualizado com a data e o resumo.

## Configuracao

Edite `entregas_config.json` para incluir novos nucleos ou alterar caminhos.

Campos principais por nucleo:

- `id` — nome da pasta em `resultados/`
- `processo` — numero REURB (ex.: `051201571/2026`)
- `bairro_pasta` — nome da pasta em `03_ENTREGAS/Peri_Mirim/`
- `status_entrega` — texto exibido no STATUS_ENTREGA.txt

## Instrucoes no Drive do cliente

A documentacao voltada ao cliente fica no Google Drive dele:

```text
H:\Meu Drive\Entregas_ITERMA_REURB\00_DOCS\INSTRUCOES.txt
```

Este script e a documentacao deste repositorio sao de uso interno da equipe
de elaboracao. O cliente trabalha apenas com as pastas do Drive.

## Fluxo recomendado

1. Gerar documentos no ArcGIS Pro (`GerarPlantaNucleoTool`, pranchas, memoriais)
2. Rodar `python sincronizar_entregas_drive.py --todos`
3. Conferir `STATUS_ENTREGA.txt` e checklist em `00_DOCS/`
4. Registrar observacoes em `01_COMENTARIOS_REVISAO/`
5. Compactar a pasta do nucleo em `03_ENTREGAS/` e enviar

## Observacoes

- O script **nao apaga** arquivos antigos no Drive; apenas sobrescreve arquivos com o mesmo nome.
- Arquivos ainda nao gerados (ex.: `planta_vertices` integral) simplesmente nao aparecem na entrega.
- Memoriais de sistema viario ficam em `05_sistema_viario/` ate definicao dos cruzamentos.

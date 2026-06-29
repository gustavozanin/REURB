# -*- coding: utf-8 -*-
"""
Copia resultados do REURB para o Google Drive, separando entrega formal e arquivos internos.

Uso:
  python sincronizar_entregas_drive.py --todos
  python sincronizar_entregas_drive.py --nucleo campo_de_pouso_051201571_2026
  python sincronizar_entregas_drive.py --todos --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path


CONFIG_PADRAO = Path(__file__).with_name("entregas_config.json")


@dataclass
class DestinoArquivo:
    origem: Path
    destino_relativo: str
    categoria: str


def processo_slug(processo: str) -> str:
    return processo.replace("/", "_")


def carregar_config(caminho: Path) -> dict:
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo de configuracao nao encontrado: {caminho}")
    return json.loads(caminho.read_text(encoding="utf-8-sig"))


def pasta_resultados_nucleo(repo_base: Path, nucleo_id: str) -> Path:
    return repo_base / "ferramentas" / "gerarplantanucleo" / "resultados" / nucleo_id


def pasta_memoriais_quadras(repo_base: Path, municipio_slug: str, bairro_slug: str, processo: str) -> Path:
    processo_pasta = processo_slug(processo)
    return (
        repo_base
        / "ferramentas"
        / "gerarplantageralbairro"
        / "resultados"
        / "memoriais_quadras"
        / municipio_slug
        / bairro_slug
        / processo_pasta
    )


def _nome_memorial_oficial(processo: str) -> str:
    return f"memorial_descritivo_{processo_slug(processo)}.pdf"


def _eh_memorial_duplicado(nome: str, processo: str) -> bool:
    oficial = _nome_memorial_oficial(processo)
    return nome.lower().startswith("memorial_descritivo_") and nome != oficial


def classificar_arquivo_nucleo(arquivo: Path, processo: str) -> tuple[str, str] | None:
    """
    Retorna (categoria_entrega, subpasta) ou None se for interno.
    categoria_entrega: 'entrega' | 'interno' via segundo valor em tupla especial.
    """
    nome = arquivo.name
    nome_lower = nome.lower()
    proc = processo_slug(processo)

    if not arquivo.is_file():
        return None

    ext = arquivo.suffix.lower()
    if ext not in {".pdf", ".zip", ".json", ".csv", ".html", ".png", ".aprx"}:
        return None

    # --- Internos (prioridade) ---
    if nome_lower.startswith("payload_"):
        return ("interno", "")
    if nome_lower == f"resultado_{proc}.json":
        return ("interno", "")
    if nome_lower.startswith("quadro_coordenadas_"):
        return ("interno", "")
    if "quadro_vertices" in nome_lower and ext == ".png":
        return ("interno", "")
    if nome_lower.startswith("planta_simplificada"):
        return ("interno", "")
    if "_mapa.pdf" in nome_lower or "_arcgis_planta.pdf" in nome_lower:
        return ("interno", "")
    if ext == ".aprx":
        return ("interno", "")
    if ext in {".csv", ".html", ".png"}:
        return ("interno", "")
    if _eh_memorial_duplicado(nome, processo):
        return ("interno", "")
    if re.match(r"^PRANCHA_02_PLANTA_", nome, flags=re.IGNORECASE):
        return ("interno", "")

    # --- Entrega ---
    if nome == _nome_memorial_oficial(processo):
        return ("entrega", "01_perimetro")

    if nome_lower.startswith("planta_vertices") and ext == ".pdf":
        return ("entrega", "01_perimetro")

    if nome_lower.startswith("quadro_vertices") and ext == ".pdf":
        return ("entrega", "01_perimetro")

    if nome_lower == f"quadro_areas_{proc}.pdf":
        return ("entrega", "02_areas")

    if nome_lower == f"quadro_areas_trabalhadas_{proc}.pdf":
        return ("entrega", "02_areas")

    if nome_lower.startswith("prancha_02-_planta_do_loteamento_") and ext == ".pdf":
        return ("entrega", "03_loteamento")

    if nome_lower.startswith("prancha_02_lista_de_beneficiarios_") and ext == ".pdf":
        return ("entrega", "03_loteamento")

    if nome_lower == f"shape_{proc}.zip":
        return ("entrega", "06_geodata")

    # Demais PDFs/JSON do nucleo vao para interno por seguranca
    return ("interno", "")


def listar_memoriais_quadras(pasta_quadras: Path) -> list[DestinoArquivo]:
    if not pasta_quadras.exists():
        return []

    destinos: list[DestinoArquivo] = []
    pdfs = pasta_quadras / "pdfs"
    if pdfs.is_dir():
        for arquivo in sorted(pdfs.glob("*.pdf")):
            destinos.append(
                DestinoArquivo(arquivo, f"04_quadras/pdfs/{arquivo.name}", "memoriais_quadras")
            )

    for arquivo in sorted(pasta_quadras.glob("MEMORIAIS_QUADRAS_*_COMPLETO.pdf")):
        destinos.append(
            DestinoArquivo(arquivo, f"04_quadras/{arquivo.name}", "memoriais_quadras")
        )

    return destinos


def garantir_pastas(base_entrega: Path, base_interno: Path) -> None:
    subpastas = [
        "01_perimetro",
        "02_areas",
        "03_loteamento",
        "04_quadras/pdfs",
        "05_sistema_viario",
        "06_geodata",
    ]
    for sub in subpastas:
        (base_entrega / sub).mkdir(parents=True, exist_ok=True)
    base_interno.mkdir(parents=True, exist_ok=True)


def copiar_arquivo(origem: Path, destino: Path, dry_run: bool) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    if dry_run:
        print(f"  [simulacao] {origem} -> {destino}")
        return
    shutil.copy2(origem, destino)


def atualizar_status_entrega(
    pasta_entrega: Path,
    nucleo: dict,
    resumo: dict,
    dry_run: bool,
) -> None:
    status_path = pasta_entrega / "STATUS_ENTREGA.txt"
    hoje = date.today().isoformat()
    texto = (
        f"STATUS DE ENTREGA — {nucleo['bairro']}\n"
        f"Processo: {nucleo['processo']}\n"
        f"Municipio: {nucleo['municipio']}\n"
        f"Responsavel pela elaboracao: {nucleo['responsavel']}\n"
        f"\n"
        f"Status geral: {nucleo['status_entrega']}\n"
        f"Ultima atualizacao dos arquivos: {hoje}\n"
        f"\n"
        f"Conteudo disponivel nesta pasta\n"
        f"-------------------------------\n"
        f"Documentos do nucleo: {resumo['entrega']} arquivo(s)\n"
        f"Memoriais de quadras: {resumo['quadras']} arquivo(s)\n"
        f"\n"
        f"Antes de revisar ou baixar, consulte:\n"
        f"  00_DOCS/INSTRUCOES.txt\n"
        f"  00_DOCS/CHECKLIST_ANTES_ENTREGA.txt\n"
        f"  01_COMENTARIOS_REVISAO/Peri_Mirim/{nucleo['bairro_pasta']}/\n"
        f"  02_MELHORIAS_PENDENTES/Peri_Mirim/{nucleo['bairro_pasta']}.txt\n"
        f"\n"
        f"Para registrar observacoes, edite ou crie um arquivo em\n"
        f"01_COMENTARIOS_REVISAO/Peri_Mirim/{nucleo['bairro_pasta']}/\n"
    )
    if dry_run:
        print(f"  [simulacao] Atualizaria {status_path}")
        return
    status_path.write_text(texto, encoding="utf-8")


def sincronizar_nucleo(config: dict, nucleo: dict, dry_run: bool) -> dict:
    repo_base = Path(config["repo_base"])
    drive_base = Path(config["drive_base"])

    origem = pasta_resultados_nucleo(repo_base, nucleo["id"])
    pasta_entrega = drive_base / "03_ENTREGAS" / nucleo["municipio_pasta"] / nucleo["bairro_pasta"]
    pasta_interno = drive_base / "04_INTERNO" / nucleo["municipio_pasta"] / nucleo["bairro_pasta"]

    print(f"\n=== {nucleo['bairro']} ({nucleo['processo']}) ===")
    if not origem.exists():
        print(f"  AVISO: pasta de resultados nao encontrada: {origem}")
        return {"entrega": 0, "interno": 0, "quadras": 0, "ignorados": 1}

    if not drive_base.exists():
        raise FileNotFoundError(
            f"Pasta do Drive nao encontrada: {drive_base}\n"
            "Verifique se o Google Drive esta sincronizado neste computador."
        )

    if not dry_run:
        garantir_pastas(pasta_entrega, pasta_interno)

    resumo = {"entrega": 0, "interno": 0, "quadras": 0, "ignorados": 0}

    for arquivo in sorted(origem.iterdir()):
        if not arquivo.is_file():
            continue
        classificacao = classificar_arquivo_nucleo(arquivo, nucleo["processo"])
        if classificacao is None:
            continue
        tipo, subpasta = classificacao
        if tipo == "entrega":
            destino = pasta_entrega / subpasta / arquivo.name
            copiar_arquivo(arquivo, destino, dry_run)
            resumo["entrega"] += 1
        else:
            destino = pasta_interno / arquivo.name
            copiar_arquivo(arquivo, destino, dry_run)
            resumo["interno"] += 1

    municipio_slug = nucleo["municipio_pasta"].lower()
    bairro_slug = nucleo.get("memoriais_quadras_slug") or nucleo["id"].split("_")[0]
    pasta_quadras = pasta_memoriais_quadras(
        repo_base,
        municipio_slug,
        bairro_slug,
        nucleo["processo"],
    )
    for item in listar_memoriais_quadras(pasta_quadras):
        destino = pasta_entrega / item.destino_relativo
        copiar_arquivo(item.origem, destino, dry_run)
        resumo["quadras"] += 1

    if resumo["quadras"] == 0 and not pasta_quadras.exists():
        resumo["ignorados"] += 1
        print(f"  INFO: memoriais de quadras nao encontrados em {pasta_quadras}")

    atualizar_status_entrega(pasta_entrega, nucleo, resumo, dry_run)
    print(
        f"  Concluido: entrega={resumo['entrega']}, interno={resumo['interno']}, "
        f"quadras={resumo['quadras']}"
    )
    return resumo


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sincroniza resultados REURB com a pasta de entregas no Google Drive."
    )
    parser.add_argument(
        "--config",
        default=str(CONFIG_PADRAO),
        help="Caminho do arquivo entregas_config.json",
    )
    parser.add_argument(
        "--nucleo",
        help="ID do nucleo (ex.: campo_de_pouso_051201571_2026). Use --todos para todos.",
    )
    parser.add_argument(
        "--todos",
        action="store_true",
        help="Sincroniza todos os nucleos do arquivo de configuracao.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra o que seria copiado, sem alterar arquivos.",
    )
    parser.add_argument(
        "--drive",
        help="Substitui o caminho drive_base do config (opcional).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.todos and not args.nucleo:
        raise SystemExit("Informe --nucleo <id> ou --todos.")

    config = carregar_config(Path(args.config))
    if args.drive:
        config["drive_base"] = args.drive

    nucleos = config.get("nucleos", [])
    if args.nucleo:
        nucleos = [n for n in nucleos if n["id"] == args.nucleo]
        if not nucleos:
            raise SystemExit(f"Nucleo nao encontrado no config: {args.nucleo}")

    print(f"Drive: {config['drive_base']}")
    print(f"Repositorio: {config['repo_base']}")
    if args.dry_run:
        print("Modo simulacao (dry-run) — nenhum arquivo sera alterado.")

    totais = {"entrega": 0, "interno": 0, "quadras": 0, "ignorados": 0}
    for nucleo in nucleos:
        resumo = sincronizar_nucleo(config, nucleo, args.dry_run)
        for chave in totais:
            totais[chave] += resumo.get(chave, 0)

    print(
        f"\nTotal: entrega={totais['entrega']}, interno={totais['interno']}, "
        f"quadras={totais['quadras']}, ignorados={totais['ignorados']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""Fecha o ZIP REURB_Plantas_v0.14.0 (local). Drive só depois do gate de teste."""
from __future__ import annotations

import argparse
import hashlib
import zipfile
from datetime import datetime
from pathlib import Path

ORIGEM = Path(r"C:\REURB\REURB_ITERMA\REURB_Plantas_v0.14.0")
VERSAO = "0.14.0"
NOME_PASTA = f"REURB_Plantas_v{VERSAO}"
DESTINO_LOCAL = Path(r"C:\REURB\REURB_ITERMA")
DESTINO_DRIVE = Path(r"H:\Meu Drive\GESTÃO_ITERMA\02_Ferramentas ArcGis Pro")
ZIP_LOCAL = DESTINO_LOCAL / f"{NOME_PASTA}.zip"
ZIP_DRIVE = DESTINO_DRIVE / f"{NOME_PASTA}.zip"

PASTAS = (
    "docs",
    "gerarmemoriaisquadras",
    "gerarplantainstitucional",
    "gerarplantaloteamento",
    "gerarplantanucleo",
    "gerarplantaverticesconfrontantesmemorial",
    "pacote_desktop",
)
ARQUIVOS = (
    "LEIA-ME_ANALISTA.txt",
    "VERSAO.txt",
    "REURB_Plantas.pyt",
    "REURB_Plantas.pyt.xml",
    "REURB_Plantas.GerarMemoriaisQuadrasDesktopTool.pyt.xml",
    "REURB_Plantas.GerarPlantaInstitucionalDesktopTool.pyt.xml",
    "REURB_Plantas.GerarPlantaLoteamentoDesktopTool.pyt.xml",
    "REURB_Plantas.GerarPlantaNucleoDesktopTool.pyt.xml",
    "REURB_Plantas.GerarPlantaVerticesConfrontantesMemorialDesktopTool.pyt.xml",
    "COMO_TESTAR_v0.14.0.txt",
    "NOTAS_TESTE_v0.14.0.txt",
    "execucao_desktop.py",
    "test_execucao_desktop.py",
)
DIRS_IGNORAR = {
    "__pycache__",
    ".git",
    ".cursor",
    ".pytest_cache",
    ".specs",
    ".vscode",
    "Index",
}
PREFIXOS_IGNORAR = (
    "automacao_",
    "diagnostico_",
    "executar_",
    "lote_",
    "_check",
)
SUFIXOS_IGNORAR = (".log", ".pyc", ".pyo", ".sde")


def deve_ignorar(caminho: Path, raiz: Path) -> bool:
    rel = caminho.relative_to(raiz)
    if any(parte in DIRS_IGNORAR for parte in rel.parts):
        return True
    nome = caminho.name.lower()
    if nome.endswith(SUFIXOS_IGNORAR):
        return True
    if "_bkp" in nome or "_backup_" in nome:
        return True
    if len(rel.parts) == 1:
        if nome.startswith(PREFIXOS_IGNORAR):
            return True
        if "v0.13" in nome:
            return True
    return False


def arquivos_para_zip() -> list[tuple[Path, str]]:
    itens: list[tuple[Path, str]] = []
    for nome in ARQUIVOS:
        src = ORIGEM / nome
        if not src.is_file():
            raise FileNotFoundError("Falta arquivo obrigatório: {}".format(src))
        itens.append((src, "{}/{}".format(NOME_PASTA, nome)))
    for pasta in PASTAS:
        raiz_pasta = ORIGEM / pasta
        if not raiz_pasta.is_dir():
            raise FileNotFoundError("Falta pasta obrigatória: {}".format(raiz_pasta))
        for src in raiz_pasta.rglob("*"):
            if src.is_dir() or deve_ignorar(src, ORIGEM):
                continue
            rel = src.relative_to(ORIGEM).as_posix()
            itens.append((src, "{}/{}".format(NOME_PASTA, rel)))
    return itens


def sha256_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--copiar-drive",
        action="store_true",
        help="Copia o ZIP para a pasta da equipe (só depois do gate de teste).",
    )
    args = parser.parse_args()

    versao = (ORIGEM / "VERSAO.txt").read_text(encoding="utf-8")
    if "versao=0.14.0" not in versao:
        raise SystemExit("VERSAO.txt da origem não é 0.14.0.")

    itens = arquivos_para_zip()
    if ZIP_LOCAL.exists():
        ZIP_LOCAL.unlink()
    print("{} Gerando {}".format(datetime.now().isoformat(timespec="seconds"), ZIP_LOCAL))
    print("Arquivos: {}".format(len(itens)))
    with zipfile.ZipFile(ZIP_LOCAL, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for src, arcname in itens:
            zf.write(src, arcname)
    digest = sha256_arquivo(ZIP_LOCAL)
    print("ZIP local: {} ({} bytes)".format(ZIP_LOCAL, ZIP_LOCAL.stat().st_size))
    print("SHA256 local: {}".format(digest))

    if args.copiar_drive:
        DESTINO_DRIVE.mkdir(parents=True, exist_ok=True)
        import shutil

        shutil.copy2(ZIP_LOCAL, ZIP_DRIVE)
        digest_drive = sha256_arquivo(ZIP_DRIVE)
        print("ZIP Drive: {} ({} bytes)".format(ZIP_DRIVE, ZIP_DRIVE.stat().st_size))
        print("SHA256 Drive: {}".format(digest_drive))
        if digest != digest_drive:
            raise SystemExit("Hash local e Drive divergem.")
        print("Pacote 0.14.0 copiado para a equipe.")
    else:
        print("Drive não atualizado. Depois do gate: python empacotar_reurb_0140.py --copiar-drive")


if __name__ == "__main__":
    main()

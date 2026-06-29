# -*- coding: utf-8 -*-

import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter


def anexar(planta_pdf, quadro_pdf):
    planta_pdf = Path(planta_pdf)
    quadro_pdf = Path(quadro_pdf)
    out_path = planta_pdf.with_name(f"{planta_pdf.stem}_com_quadro_completo.pdf")

    writer = PdfWriter()
    for path in [planta_pdf, quadro_pdf]:
        reader = PdfReader(str(path))
        for page in reader.pages:
            writer.add_page(page)

    with out_path.open("wb") as arquivo:
        writer.write(arquivo)

    return out_path


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Uso: python anexar_quadro_na_planta.py planta.pdf quadro.pdf")
    print(anexar(sys.argv[1], sys.argv[2]))

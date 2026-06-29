# -*- coding: utf-8 -*-

from pathlib import Path
import arcpy


APRX_ITERMA = Path(
    r"C:\Users\gusta\OneDrive\Documentos\ArcGIS\Projects\REURB_ITERMA\REURB_ITERMA.aprx"
)
SHP_DIR = Path(r"C:\REURB\SHP")


def _mensagem(texto):
    try:
        arcpy.AddMessage(texto)
    except Exception:
        print(texto)


def _avisar(texto):
    try:
        arcpy.AddWarning(texto)
    except Exception:
        print(f"AVISO: {texto}")


def _campo_por_nome(feature_class, candidatos):
    campos = {field.name.lower(): field.name for field in arcpy.ListFields(feature_class)}
    for candidato in candidatos:
        if candidato.lower() in campos:
            return campos[candidato.lower()]
    return None


def _primeira_camada(aprx, nome):
    for mapa in aprx.listMaps():
        for camada in mapa.listLayers(nome):
            if camada.isFeatureLayer:
                return camada
    raise RuntimeError(f"Camada '{nome}' nao encontrada em {APRX_ITERMA}")


def _remover_saida(caminho_saida):
    if arcpy.Exists(str(caminho_saida)):
        arcpy.management.Delete(str(caminho_saida))


def exportar_camada(aprx, nome_camada, caminho_saida):
    camada = _primeira_camada(aprx, nome_camada)
    _remover_saida(caminho_saida)
    arcpy.management.CopyFeatures(camada, str(caminho_saida))
    quantidade = int(arcpy.management.GetCount(str(caminho_saida))[0])
    _mensagem(f"{nome_camada} exportada: {caminho_saida} ({quantidade} feicoes)")
    return str(caminho_saida)


def _mesmo_ponto(ponto_a, ponto_b):
    return ponto_a and ponto_b and ponto_a.X == ponto_b.X and ponto_a.Y == ponto_b.Y


def gerar_vertices_bairro(bairro_shp, vertices_saida):
    _remover_saida(vertices_saida)

    referencia = arcpy.Describe(bairro_shp).spatialReference
    arcpy.management.CreateFeatureclass(
        out_path=str(vertices_saida.parent),
        out_name=vertices_saida.name,
        geometry_type="POINT",
        spatial_reference=referencia,
        has_m="DISABLED",
        has_z="DISABLED",
    )
    arcpy.management.AddField(str(vertices_saida), "n_coletivo", "TEXT", field_length=50)
    arcpy.management.AddField(str(vertices_saida), "bairro", "TEXT", field_length=120)
    arcpy.management.AddField(str(vertices_saida), "vertice", "TEXT", field_length=20)
    arcpy.management.AddField(str(vertices_saida), "parte", "LONG")
    arcpy.management.AddField(str(vertices_saida), "ordem", "LONG")

    campo_n_coletivo = _campo_por_nome(bairro_shp, ["n_coletivo", "ncoletivo"])
    campo_bairro = _campo_por_nome(bairro_shp, ["bairro", "nome", "nm_bairro"])
    campos_leitura = ["SHAPE@"]
    if campo_n_coletivo:
        campos_leitura.append(campo_n_coletivo)
    if campo_bairro:
        campos_leitura.append(campo_bairro)

    total = 0
    with arcpy.da.InsertCursor(
        str(vertices_saida),
        ["SHAPE@", "n_coletivo", "bairro", "vertice", "parte", "ordem"],
    ) as insert_cursor:
        with arcpy.da.SearchCursor(bairro_shp, campos_leitura) as search_cursor:
            for row in search_cursor:
                geometria = row[0]
                if not geometria:
                    _avisar("Feicao de bairro sem geometria ignorada na exportacao de vertices.")
                    continue

                n_coletivo = row[campos_leitura.index(campo_n_coletivo)] if campo_n_coletivo else None
                bairro = row[campos_leitura.index(campo_bairro)] if campo_bairro else None

                ordem_global = 1
                for indice_parte, parte in enumerate(geometria, start=1):
                    pontos = [ponto for ponto in parte if ponto]
                    if len(pontos) > 1 and _mesmo_ponto(pontos[0], pontos[-1]):
                        pontos = pontos[:-1]

                    for ponto in pontos:
                        insert_cursor.insertRow(
                            [
                                arcpy.PointGeometry(ponto, referencia),
                                n_coletivo,
                                bairro,
                                f"V{ordem_global}",
                                indice_parte,
                                ordem_global,
                            ]
                        )
                        ordem_global += 1
                        total += 1

    _mensagem(f"Vertices do perimetro exportados: {vertices_saida} ({total} pontos)")
    return str(vertices_saida)


def main():
    if not APRX_ITERMA.exists():
        raise FileNotFoundError(f"APRX nao encontrado: {APRX_ITERMA}")

    SHP_DIR.mkdir(parents=True, exist_ok=True)
    arcpy.env.overwriteOutput = True

    aprx = arcpy.mp.ArcGISProject(str(APRX_ITERMA))
    bairro_shp = exportar_camada(aprx, "Bairro", SHP_DIR / "bairro_camada.shp")
    eixo_shp = exportar_camada(aprx, "Eixo Viario", SHP_DIR / "eixo_viario_Peri Mirim.shp")
    vertices_shp = gerar_vertices_bairro(bairro_shp, SHP_DIR / "bairro_vertices_perimetro.shp")

    _mensagem("Exportacao concluida.")
    _mensagem(f"Bairro: {bairro_shp}")
    _mensagem(f"Eixo viario: {eixo_shp}")
    _mensagem(f"Vertices: {vertices_shp}")


if __name__ == "__main__":
    main()

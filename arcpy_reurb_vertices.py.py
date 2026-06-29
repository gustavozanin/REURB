import arcpy
import os

# Permite sobrescrever saídas existentes
arcpy.env.overwriteOutput = True

# Caminhos de entrada
bairro_in = r"C:\REURB\SHP\bairro_exp.shp"
quadra_in = r"C:\REURB\SHP\Quadra_exp.shp"

# Geodatabase de saída
out_gdb = r"C:\REURB\reurb.gdb"

# Saídas reprojetadas
bairro_out = os.path.join(out_gdb, "bairro_exp_utm")
quadra_out = os.path.join(out_gdb, "Quadra_exp_utm")

# Sistemas de coordenadas
sr_origem = arcpy.SpatialReference(4674)   # SIRGAS 2000 geográfico
sr_destino = arcpy.SpatialReference(31983) # SIRGAS 2000 / UTM Zone 23S

# Garante que a geodatabase existe
if not arcpy.Exists(out_gdb):
    arcpy.management.CreateFileGDB(r"C:\REURB", "reurb.gdb")

# Como sua camada já aparece com EPSG 4674, esta etapa é só preventiva.
# Se o shapefile já tiver projeção correta, o ArcGIS apenas mantém/avisa.
print("Definindo projeção original como SIRGAS 2000 geográfico...")
arcpy.management.DefineProjection(bairro_in, sr_origem)
arcpy.management.DefineProjection(quadra_in, sr_origem)

# Reprojeta para UTM 23S
print("Reprojetando bairro_exp para SIRGAS 2000 / UTM Zone 23S...")
arcpy.management.Project(
    in_dataset=bairro_in,
    out_dataset=bairro_out,
    out_coor_system=sr_destino
)

print("Reprojetando Quadra_exp para SIRGAS 2000 / UTM Zone 23S...")
arcpy.management.Project(
    in_dataset=quadra_in,
    out_dataset=quadra_out,
    out_coor_system=sr_destino
)

print("Concluído.")
print(f"Bairro UTM: {bairro_out}")
print(f"Quadras UTM: {quadra_out}")


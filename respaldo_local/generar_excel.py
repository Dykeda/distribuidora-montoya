"""Genera un Excel legible a partir de una copia de la base de datos (.db).

No reemplaza el respaldo real (el .db es la fuente de verdad y lo que se
usaría para restaurar el sistema) — esto es una foto adicional, en texto
plano, para poder abrir y revisar la información sin nada técnico si el
servidor llegara a fallar.

Uso: generar_excel.py <ruta_al_db> <ruta_al_xlsx_salida>
"""
import sys


def generar(ruta_db, ruta_salida):
    sys.path.insert(0, r"C:\Users\Kevin P\Documents\distribuidora-montoya")
    from app import create_app
    from services.exportar import construir_workbook

    app = create_app(config_overrides={"SQLALCHEMY_DATABASE_URI": "sqlite:///" + ruta_db})

    with app.app_context():
        wb = construir_workbook()

    wb.save(ruta_salida)
    print(f"Excel generado en: {ruta_salida}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: generar_excel.py <ruta_al_db> <ruta_al_xlsx_salida>")
        raise SystemExit(1)
    generar(sys.argv[1], sys.argv[2])

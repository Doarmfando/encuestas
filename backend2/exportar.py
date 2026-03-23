"""
Exportador de resultados a Excel - usa utilidades compartidas.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.excel_utils import (
    crear_workbook,
    escribir_headers,
    escribir_fila,
    escribir_resumen,
    guardar_excel,
)


def exportar_excel(registros, resumen, estructura):
    """Exporta los datos a Excel."""
    wb = crear_workbook()

    # ===== HOJA 1: RESPUESTAS =====
    ws = wb.active
    ws.title = "Respuestas"

    # Recopilar preguntas como headers
    preguntas_headers = []
    for pagina in estructura.get("paginas", []):
        for preg in pagina.get("preguntas", []):
            if preg["tipo"] != "informativo":
                preguntas_headers.append(preg["texto"])

    headers = ["#", "Estado", "Tiempo (s)", "Perfil", "Tendencia"] + preguntas_headers
    escribir_headers(ws, headers)

    # Datos
    for fila, reg in enumerate(registros, 2):
        datos = [
            reg["numero"],
            "Exitosa" if reg["exito"] else "Fallida",
            f"{reg['tiempo']:.1f}",
            reg.get("perfil", ""),
            reg.get("tendencia", ""),
        ]

        valores = {}
        for pagina in reg["respuestas"].get("paginas", []):
            for r in pagina.get("respuestas", []):
                valores[r["pregunta"]] = r["valor"]

        for preg in preguntas_headers:
            datos.append(valores.get(preg, ""))

        escribir_fila(ws, fila, datos, col_estado=2)

    ws.column_dimensions["A"].width = 5
    ws.column_dimensions["B"].width = 10
    ws.column_dimensions["C"].width = 10
    ws.column_dimensions["D"].width = 20
    ws.column_dimensions["E"].width = 18

    # ===== HOJA 2: RESUMEN =====
    ws2 = wb.create_sheet("Resumen")
    datos_resumen = [
        ("Fecha", resumen["fecha"]),
        ("Total", resumen["total"]),
        ("Exitosas", resumen["exitosas"]),
        ("Fallidas", resumen["fallidas"]),
        ("Tasa de éxito", f"{resumen['tasa_exito']:.1f}%"),
        ("Tiempo total", resumen["tiempo_total_fmt"]),
        ("Tiempo promedio", resumen["tiempo_promedio_fmt"]),
    ]
    escribir_resumen(ws2, datos_resumen)

    return guardar_excel(wb, os.path.dirname(__file__))

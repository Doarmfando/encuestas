"""
Servidor API para el servicio universal de encuestas.
"""
import sys
import os
import time
import json
import threading
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.browser_utils import formatear_tiempo

from scraper import scrape_formulario
from analizador import analizar_encuesta
from bot import ejecutar_bot

app = Flask(__name__)
CORS(app)

# Estado global
estado = {
    "fase": "idle",  # idle, scrapeando, analizando, ejecutando, completado
    "mensaje": "Listo",
    "progreso": 0,
    "total": 0,
    "exitosas": 0,
    "fallidas": 0,
    "tiempo_transcurrido": "0s",
    "tiempo_por_encuesta": "0s",
    "excel": None,
}

# Datos en memoria
datos = {
    "estructura": None,
    "configuracion": None,
    "url": None,
}

_inicio = None


# ============ SCRAPING ============

@app.route("/api/scrape", methods=["POST"])
def scrape():
    """Scrapea un formulario de Google Forms."""
    data = request.json or {}
    url = data.get("url", "")

    if not url:
        return jsonify({"error": "URL requerida"}), 400

    estado["fase"] = "scrapeando"
    estado["mensaje"] = "Scrapeando formulario..."

    try:
        estructura = scrape_formulario(url, headless=True)

        if estructura.get("requiere_login"):
            estado["fase"] = "idle"
            return jsonify({"error": "Este formulario requiere login de Google. Solo se soportan formularios públicos."}), 400

        datos["estructura"] = estructura
        datos["url"] = estructura["url"]
        estado["fase"] = "idle"
        estado["mensaje"] = f"Scrapeado: {estructura['total_preguntas']} preguntas"

        return jsonify(estructura)

    except Exception as e:
        estado["fase"] = "idle"
        estado["mensaje"] = f"Error: {str(e)}"
        return jsonify({"error": str(e)}), 500


# ============ ANÁLISIS CON GPT ============

@app.route("/api/analizar", methods=["POST"])
def analizar():
    """Analiza el formulario scrapeado con GPT."""
    if not datos["estructura"]:
        return jsonify({"error": "Primero scrapea un formulario"}), 400

    estado["fase"] = "analizando"
    estado["mensaje"] = "GPT analizando encuesta..."

    try:
        configuracion = analizar_encuesta(datos["estructura"])
        datos["configuracion"] = configuracion
        estado["fase"] = "idle"
        estado["mensaje"] = "Análisis completado"

        return jsonify(configuracion)

    except Exception as e:
        estado["fase"] = "idle"
        return jsonify({"error": str(e)}), 500


# ============ CONFIGURACIÓN (editar perfiles) ============

@app.route("/api/configuracion", methods=["GET"])
def obtener_config():
    """Devuelve la configuración actual."""
    if datos["configuracion"]:
        return jsonify(datos["configuracion"])
    return jsonify({"error": "No hay configuración"}), 404


@app.route("/api/configuracion", methods=["PUT"])
def actualizar_config():
    """Actualiza la configuración (perfiles, reglas, tendencias editadas por el usuario)."""
    nueva_config = request.json
    if not nueva_config:
        return jsonify({"error": "Configuración vacía"}), 400

    datos["configuracion"] = nueva_config
    return jsonify({"mensaje": "Configuración actualizada"})


@app.route("/api/estructura", methods=["GET"])
def obtener_estructura():
    """Devuelve la estructura scrapeada."""
    if datos["estructura"]:
        return jsonify(datos["estructura"])
    return jsonify({"error": "No hay estructura"}), 404


# ============ EJECUCIÓN DEL BOT ============

def actualizar_progreso(actual, total, exitosas, fallidas):
    global _inicio
    estado["progreso"] = actual
    estado["total"] = total
    estado["exitosas"] = exitosas
    estado["fallidas"] = fallidas
    estado["mensaje"] = f"Encuesta {actual}/{total}"
    if _inicio:
        transcurrido = time.time() - _inicio
        estado["tiempo_transcurrido"] = formatear_tiempo(transcurrido)
        if actual > 0:
            estado["tiempo_por_encuesta"] = formatear_tiempo(transcurrido / actual)


def ejecutar_en_hilo(url, configuracion, estructura, cantidad, headless):
    global _inicio
    _inicio = time.time()
    estado["fase"] = "ejecutando"
    estado["progreso"] = 0
    estado["total"] = cantidad
    estado["exitosas"] = 0
    estado["fallidas"] = 0
    estado["excel"] = None

    try:
        resultado = ejecutar_bot(
            url=url,
            configuracion=configuracion,
            estructura=estructura,
            cantidad=cantidad,
            headless=headless,
            callback=actualizar_progreso,
        )
        estado["mensaje"] = f"Completado: {resultado['exitosas']}/{resultado['total']} en {resultado['tiempo_total']}"
        estado["excel"] = resultado.get("excel")
        estado["fase"] = "completado"
    except Exception as e:
        estado["mensaje"] = f"Error: {str(e)}"
        estado["fase"] = "idle"


@app.route("/api/ejecutar", methods=["POST"])
def ejecutar():
    """Inicia la ejecución del bot."""
    if estado["fase"] == "ejecutando":
        return jsonify({"error": "Ya hay una ejecución en curso"}), 400

    if not datos["configuracion"] or not datos["estructura"]:
        return jsonify({"error": "Primero scrapea y analiza el formulario"}), 400

    data = request.json or {}
    cantidad = data.get("cantidad", 10)
    headless = data.get("headless", False)

    if cantidad < 1 or cantidad > 500:
        return jsonify({"error": "Cantidad debe ser entre 1 y 500"}), 400

    hilo = threading.Thread(
        target=ejecutar_en_hilo,
        args=(datos["url"], datos["configuracion"], datos["estructura"], cantidad, headless),
    )
    hilo.daemon = True
    hilo.start()

    return jsonify({"mensaje": f"Bot iniciado: {cantidad} encuestas"})


@app.route("/api/estado", methods=["GET"])
def obtener_estado():
    return jsonify(estado)


@app.route("/api/detener", methods=["POST"])
def detener():
    estado["fase"] = "idle"
    estado["mensaje"] = "Detenido"
    return jsonify({"mensaje": "Detenido"})


@app.route("/api/descargar", methods=["GET"])
def descargar():
    if estado["excel"] and os.path.exists(estado["excel"]):
        return send_file(estado["excel"], as_attachment=True)
    return jsonify({"error": "No hay Excel"}), 404


if __name__ == "__main__":
    print("🚀 Servidor Universal en http://localhost:5001")
    app.run(debug=False, port=5001)

"""
Bot que llena formularios de Google Forms usando las respuestas generadas.
Navega página por página, detecta botones y llena todo.
"""
import sys
import os
import random
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

# Agregar shared al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.browser_utils import (
    formatear_tiempo,
    click_opcion,
    escribir_texto,
    click_boton,
    verificar_envio,
    responder_escala_likert,
)


def llenar_formulario(page, respuesta_generada, url, numero):
    """Llena un formulario completo con la respuesta generada."""
    inicio = time.time()
    perfil = respuesta_generada.get("_perfil", "?")
    tendencia = respuesta_generada.get("_tendencia", "?")

    print(f"\n{'='*55}")
    print(f"  ENCUESTA #{numero} | Perfil: {perfil} | Tendencia: {tendencia}")
    print(f"{'='*55}")

    page.goto(url)
    page.wait_for_load_state("networkidle")
    time.sleep(3)

    paginas = respuesta_generada.get("paginas", [])

    for pag_idx, pagina in enumerate(paginas):
        print(f"  [Pág {pag_idx + 1}/{len(paginas)}]")
        time.sleep(1)

        respuestas = pagina.get("respuestas", [])
        escalas_pendientes = []

        for resp in respuestas:
            tipo = resp["tipo"]
            valor = resp["valor"]
            pregunta = resp["pregunta"]

            if tipo == "opcion_multiple":
                print(f"    {pregunta}: {valor}")
                click_opcion(page, valor)
                time.sleep(0.5)

            elif tipo == "seleccion_multiple":
                print(f"    {pregunta}: {valor}")
                click_opcion(page, valor)
                time.sleep(0.5)

            elif tipo in ("texto", "numero"):
                print(f"    {pregunta}: {valor}")
                escribir_texto(page, valor)
                time.sleep(0.5)

            elif tipo == "escala_lineal":
                escalas_pendientes.append(valor)

            elif tipo == "desplegable":
                print(f"    {pregunta}: {valor}")
                try:
                    dropdown = page.locator(f'[role="listbox"]:near(:text("{pregunta}"))').first
                    dropdown.click()
                    time.sleep(0.5)
                    option = page.locator(f'[role="option"]:has-text("{valor}")').first
                    option.click()
                except Exception:
                    pass
                time.sleep(0.5)

        if escalas_pendientes:
            print(f"    Respondiendo {len(escalas_pendientes)} escalas...")
            responder_escala_likert(page, escalas_pendientes)

        # Click en el botón correspondiente
        botones = pagina.get("botones", [])
        if "Siguiente" in botones:
            click_boton(page, "Siguiente")
        elif "Enviar" in botones:
            click_boton(page, "Enviar")

    # Verificar envío
    exito = verificar_envio(page)
    tiempo = time.time() - inicio

    if exito:
        print(f"  ✅ Enviada! ⏱️ {formatear_tiempo(tiempo)}")
    else:
        print(f"  ⚠️ No confirmada ⏱️ {formatear_tiempo(tiempo)}")

    return exito, tiempo


def ejecutar_bot(url, configuracion, estructura, cantidad=10, headless=False, callback=None):
    """Ejecuta el bot completo."""
    from generador import generar_respuesta
    from exportar import exportar_excel

    exitosas = 0
    fallidas = 0
    registros = []
    tiempo_total_inicio = time.time()

    print(f"\n🤖 Bot Universal - {cantidad} respuestas")
    print(f"   URL: {url[:60]}...")
    print(f"   Modo: {'Invisible' if headless else 'Visible'}")
    print(f"   Inicio: {datetime.now().strftime('%H:%M:%S')}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            locale="es-PE",
            timezone_id="America/Lima",
            viewport={"width": 1280, "height": 720},
        )

        for i in range(1, cantidad + 1):
            page = context.new_page()
            respuesta = generar_respuesta(configuracion, estructura)

            try:
                exito, tiempo = llenar_formulario(page, respuesta, url, i)
                if exito:
                    exitosas += 1
                else:
                    fallidas += 1
            except Exception as e:
                print(f"  ❌ Error #{i}: {e}")
                exito = False
                tiempo = time.time() - tiempo_total_inicio
                fallidas += 1
            finally:
                page.close()

            registros.append({
                "numero": i,
                "exito": exito,
                "tiempo": tiempo,
                "perfil": respuesta.get("_perfil", ""),
                "tendencia": respuesta.get("_tendencia", ""),
                "respuestas": respuesta,
            })

            if callback:
                callback(i, cantidad, exitosas, fallidas)

            tiempo_total = time.time() - tiempo_total_inicio
            promedio = tiempo_total / i
            restante = promedio * (cantidad - i)

            print(f"  📊 {i}/{cantidad} | ✅ {exitosas} ❌ {fallidas} | "
                  f"⏱️ {formatear_tiempo(tiempo_total)} | "
                  f"⏳ ~{formatear_tiempo(restante)}")

            if i < cantidad:
                pausa = random.uniform(3, 8)
                print(f"  💤 {pausa:.1f}s...")
                time.sleep(pausa)

        browser.close()

    tiempo_final = time.time() - tiempo_total_inicio
    tasa = (exitosas / cantidad * 100) if cantidad > 0 else 0
    promedio_final = tiempo_final / cantidad if cantidad > 0 else 0

    print(f"\n{'='*55}")
    print(f"  RESUMEN: {exitosas}/{cantidad} exitosas ({tasa:.0f}%)")
    print(f"  Tiempo: {formatear_tiempo(tiempo_final)} total | {formatear_tiempo(promedio_final)} promedio")
    print(f"{'='*55}")

    resumen = {
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": cantidad,
        "exitosas": exitosas,
        "fallidas": fallidas,
        "tasa_exito": tasa,
        "tiempo_total_fmt": formatear_tiempo(tiempo_final),
        "tiempo_promedio_fmt": formatear_tiempo(promedio_final),
    }

    ruta_excel = exportar_excel(registros, resumen, estructura)

    return {
        "exitosas": exitosas,
        "fallidas": fallidas,
        "total": cantidad,
        "tiempo_total": formatear_tiempo(tiempo_final),
        "tiempo_promedio": formatear_tiempo(promedio_final),
        "excel": ruta_excel,
    }

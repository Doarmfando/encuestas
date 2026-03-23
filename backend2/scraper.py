"""
Scraper de Google Forms - Legacy entry point.
Delega a los módulos modernos (FBDataStrategy) y mantiene la lógica
de combinación de resultados y navegación Playwright.
"""
import re
import json
import sys
import os
import time
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.browser_utils import detectar_botones, llenar_dummy_pagina

from app.constants.question_types import GOOGLE_FORMS_TYPE_MAP
from app.scraping.strategies.fb_data import FBDataStrategy

_fb_strategy = FBDataStrategy()


def scrape_formulario(url, headless=True):
    """Scrapea un Google Form extrayendo los datos del HTML fuente."""
    resultado = _resultado_vacio(url)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            locale="es-PE",
            timezone_id="America/Lima",
            viewport={"width": 1280, "height": 720},
        )
        page = context.new_page()

        page.goto(url, wait_until="networkidle")
        time.sleep(2)

        # Detectar login requerido
        if "accounts.google.com" in page.url:
            resultado["requiere_login"] = True
            browser.close()
            return resultado

        resultado["url"] = page.url

        # ============ MÉTODO 1: FB_PUBLIC_LOAD_DATA_ (delegado) ============
        html = page.content()
        resultado_fb = _fb_strategy.extract(html, resultado["url"])

        if resultado_fb:
            print(f"  [Método 1] FB_DATA: {resultado_fb['total_preguntas']} preguntas en {len(resultado_fb['paginas'])} páginas")

        # ============ MÉTODO 2: Navegación Playwright ============
        print("  [Método 2] Navegación directa con Playwright...")
        resultado_pw = _scrape_navegando(page, resultado["url"])
        print(f"    → {resultado_pw['total_preguntas']} preguntas en {len(resultado_pw['paginas'])} páginas")

        browser.close()

    # ============ COMBINAR: elegir la mejor estrategia ============
    if resultado_fb and resultado_pw:
        fb_paginas = len(resultado_fb["paginas"])
        pw_paginas = len(resultado_pw["paginas"])
        fb_preguntas = resultado_fb["total_preguntas"]
        pw_preguntas = resultado_pw["total_preguntas"]

        print(f"\n  Comparando: FB_DATA={fb_preguntas}preg/{fb_paginas}pág vs Playwright={pw_preguntas}preg/{pw_paginas}pág")

        if pw_paginas > 1 and pw_paginas > fb_paginas:
            resultado = _redistribuir_en_paginas(resultado_fb, resultado_pw)
            print(f"  → Preguntas de FB_DATA en estructura de {pw_paginas} páginas de Playwright")
        elif fb_paginas > 1 and fb_paginas >= pw_paginas:
            resultado = _combinar_resultados(resultado_fb, resultado_pw)
            print(f"  → FB_DATA como base ({fb_paginas} páginas)")
        elif fb_preguntas > pw_preguntas:
            resultado = _combinar_resultados(resultado_fb, resultado_pw)
            print(f"  → FB_DATA como base (más preguntas)")
        else:
            resultado = _combinar_resultados(resultado_pw, resultado_fb)
            print(f"  → Playwright como base")
    elif resultado_fb:
        resultado = resultado_fb
        print(f"\n  Usando solo FB_DATA")
    elif resultado_pw["total_preguntas"] > 0:
        resultado = resultado_pw
        print(f"\n  Usando solo Playwright")
    else:
        print("\n  Ningún método capturó preguntas, usando fallback HTML...")
        resultado = _parsear_html_fallback(html, resultado)

    print(f"\n  Scraping completado:")
    print(f"    Páginas: {len(resultado['paginas'])}")
    print(f"    Preguntas: {resultado['total_preguntas']}")

    return resultado


def _resultado_vacio(url=""):
    """Crea un resultado vacío."""
    return {
        "url": url, "titulo": "", "descripcion": "",
        "paginas": [], "total_preguntas": 0, "requiere_login": False,
    }


def _scrape_navegando(page, url):
    """Método 2: Scrapea navegando página por página con Playwright."""
    resultado = _resultado_vacio(url)

    page.goto(url, wait_until="networkidle")
    time.sleep(2)

    try:
        titulo_el = page.locator('[role="heading"]').first
        if titulo_el.count() > 0:
            resultado["titulo"] = titulo_el.inner_text().strip()
    except Exception:
        pass

    num_pagina = 1
    max_paginas = 20
    paginas_vistas = set()

    while num_pagina <= max_paginas:
        try:
            texto_pagina = page.locator('[role="list"]').inner_text() if page.locator('[role="list"]').count() > 0 else ""
            hash_pagina = hash(texto_pagina)
        except Exception:
            hash_pagina = hash(str(num_pagina))

        if hash_pagina in paginas_vistas:
            break
        paginas_vistas.add(hash_pagina)

        pagina_data = {"numero": num_pagina, "preguntas": [], "botones": []}

        items = page.locator('[role="listitem"]').all()
        for item in items:
            pregunta = _extraer_pregunta_playwright(item)
            if pregunta:
                pagina_data["preguntas"].append(pregunta)
                resultado["total_preguntas"] += 1

        pagina_data["botones"] = detectar_botones(page)
        resultado["paginas"].append(pagina_data)

        if "Siguiente" in pagina_data["botones"]:
            llenar_dummy_pagina(page)
            time.sleep(0.5)
            try:
                btn = page.locator('span:has-text("Siguiente"), [role="button"]:has-text("Siguiente")').first
                btn.click()
                time.sleep(2)
                page.wait_for_load_state("networkidle")
                time.sleep(1)
            except Exception:
                break
            num_pagina += 1
        else:
            break

    return resultado


def _extraer_pregunta_playwright(item):
    """Extrae una pregunta de un elemento del DOM con detección completa de tipos."""
    try:
        texto = item.inner_text().strip()
        if not texto or len(texto) < 3:
            return None

        pregunta = {
            "texto": "",
            "tipo": "desconocido",
            "obligatoria": False,
            "opciones": [],
        }

        lineas = texto.split("\n")
        pregunta["texto"] = lineas[0].strip().replace(" *", "")
        pregunta["obligatoria"] = "*" in texto

        # Detectar opción "Otro"
        tiene_otro = False
        try:
            otro = item.locator('[aria-label="Otro"], [aria-label="Other"], input[type="text"][aria-label*="Otro"]')
            if otro.count() > 0:
                tiene_otro = True
        except Exception:
            pass

        # Radios
        radios = item.locator('[role="radio"]').all()
        if radios:
            is_scale = _detect_scale_pw(radios)
            if is_scale:
                pregunta["tipo"] = "escala_lineal"
                for radio in radios:
                    label = radio.get_attribute("aria-label") or radio.get_attribute("data-value") or ""
                    if label.strip():
                        pregunta["opciones"].append(label.strip())
            else:
                pregunta["tipo"] = "opcion_multiple"
                for radio in radios:
                    label = radio.get_attribute("aria-label") or ""
                    if label.strip():
                        pregunta["opciones"].append(label.strip())
                if not pregunta["opciones"]:
                    for lbl in item.locator('.docssharedWizToggleLabeledContent, [data-value]').all():
                        t = lbl.inner_text().strip() or lbl.get_attribute("data-value") or ""
                        if t and t not in pregunta["opciones"]:
                            pregunta["opciones"].append(t)

            if tiene_otro:
                pregunta["tiene_otro"] = True
                if "Otro" not in pregunta["opciones"]:
                    pregunta["opciones"].append("Otro")
            return pregunta

        # Checkboxes
        checks = item.locator('[role="checkbox"]').all()
        if checks:
            pregunta["tipo"] = "seleccion_multiple"
            for c in checks:
                label = c.get_attribute("aria-label") or ""
                if label.strip():
                    pregunta["opciones"].append(label.strip())
            if tiene_otro:
                pregunta["tiene_otro"] = True
                if "Otro" not in pregunta["opciones"]:
                    pregunta["opciones"].append("Otro")
            return pregunta

        # Matriz/Grid
        try:
            rows = item.locator('[role="radiogroup"], [role="group"]').all()
            if len(rows) > 1:
                first_radios = rows[0].locator('[role="radio"]').all()
                first_checks = rows[0].locator('[role="checkbox"]').all()
                pregunta["tipo"] = "matriz_checkbox" if first_checks else "matriz"
                for r in (first_radios or first_checks):
                    label = r.get_attribute("aria-label") or ""
                    if label.strip() and label.strip() not in pregunta["opciones"]:
                        pregunta["opciones"].append(label.strip())
                filas = []
                for row in rows:
                    row_label = row.get_attribute("aria-label") or ""
                    if row_label.strip():
                        filas.append(row_label.strip())
                if filas:
                    pregunta["filas"] = filas
                return pregunta
        except Exception:
            pass

        # Fecha
        try:
            date_inputs = item.locator('input[type="date"], [aria-label*="Día"], [aria-label*="Day"], [aria-label*="Mes"], [aria-label*="Month"]')
            if date_inputs.count() > 0:
                pregunta["tipo"] = "fecha"
                return pregunta
        except Exception:
            pass

        # Hora
        try:
            time_inputs = item.locator('input[type="time"], [aria-label*="Hora"], [aria-label*="Hour"], [aria-label*="Minuto"], [aria-label*="Minute"]')
            if time_inputs.count() > 0:
                pregunta["tipo"] = "hora"
                return pregunta
        except Exception:
            pass

        # Archivo
        try:
            file_inputs = item.locator('input[type="file"], button:has-text("Agregar archivo"), button:has-text("Add file")')
            if file_inputs.count() > 0:
                pregunta["tipo"] = "archivo"
                pregunta["no_llenar"] = True
                return pregunta
        except Exception:
            pass

        # Número
        if item.locator('input[type="number"]').count() > 0:
            pregunta["tipo"] = "numero"
            return pregunta

        # Párrafo
        if item.locator('textarea').count() > 0:
            pregunta["tipo"] = "parrafo"
            return pregunta

        # Texto
        if item.locator('input[type="text"]').count() > 0:
            pregunta["tipo"] = "texto"
            return pregunta

        # Dropdown
        if item.locator('[role="listbox"]').count() > 0:
            pregunta["tipo"] = "desplegable"
            try:
                options = item.locator('[role="option"]').all()
                for opt in options:
                    t = opt.get_attribute("data-value") or opt.inner_text().strip()
                    if t and t not in pregunta["opciones"] and t != "Elige":
                        pregunta["opciones"].append(t)
            except Exception:
                pass
            return pregunta

        # Informativo
        if len(texto) > 5:
            pregunta["tipo"] = "informativo"
            return pregunta

        return None
    except Exception:
        return None


def _detect_scale_pw(radios) -> bool:
    """Detecta si radios forman una escala lineal numérica."""
    try:
        if len(radios) < 3 or len(radios) > 11:
            return False
        values = []
        for radio in radios:
            val = radio.get_attribute("data-value") or radio.get_attribute("aria-label") or ""
            val = val.strip()
            if val.isdigit():
                values.append(int(val))
        if len(values) >= 3:
            sorted_vals = sorted(values)
            return all(sorted_vals[i] == sorted_vals[0] + i for i in range(len(sorted_vals)))
        return False
    except Exception:
        return False


# ============ COMBINACIÓN DE RESULTADOS ============

def _redistribuir_en_paginas(fb_result, pw_result):
    """Toma las preguntas de FB_DATA y las distribuye en la estructura de páginas de Playwright."""
    resultado = _resultado_vacio(fb_result["url"])
    resultado["titulo"] = fb_result["titulo"] or pw_result["titulo"]
    resultado["descripcion"] = fb_result["descripcion"] or pw_result["descripcion"]

    todas_fb = []
    for pag in fb_result["paginas"]:
        for preg in pag["preguntas"]:
            todas_fb.append(preg)

    preguntas_pw_keys = set()
    for pag in pw_result["paginas"]:
        for preg in pag["preguntas"]:
            preguntas_pw_keys.add(preg["texto"].lower().strip()[:50])

    fb_por_texto = {}
    for preg in todas_fb:
        key = preg["texto"].lower().strip()[:50]
        fb_por_texto[key] = preg

    paginas_finales = []
    fb_idx = 0

    for pag_pw in pw_result["paginas"]:
        huerfanas_antes = []
        primera_preg_pw = pag_pw["preguntas"][0]["texto"].lower().strip()[:50] if pag_pw["preguntas"] else ""

        pos_pw_en_fb = -1
        for i, preg_fb in enumerate(todas_fb):
            if preg_fb["texto"].lower().strip()[:50] == primera_preg_pw:
                pos_pw_en_fb = i
                break

        if pos_pw_en_fb > fb_idx:
            for i in range(fb_idx, pos_pw_en_fb):
                key = todas_fb[i]["texto"].lower().strip()[:50]
                if key not in preguntas_pw_keys and todas_fb[i]["tipo"] != "informativo":
                    huerfanas_antes.append(todas_fb[i])

        if huerfanas_antes:
            paginas_finales.append({
                "numero": len(paginas_finales) + 1,
                "preguntas": huerfanas_antes,
                "botones": ["Siguiente"],
            })

        nueva_pagina = {
            "numero": len(paginas_finales) + 1,
            "preguntas": [],
            "botones": pag_pw["botones"],
        }
        for preg_pw in pag_pw["preguntas"]:
            key = preg_pw["texto"].lower().strip()[:50]
            if key in fb_por_texto:
                preg_final = fb_por_texto[key].copy()
                if not preg_final["opciones"] and preg_pw["opciones"]:
                    preg_final["opciones"] = preg_pw["opciones"]
                nueva_pagina["preguntas"].append(preg_final)
            else:
                nueva_pagina["preguntas"].append(preg_pw)

        paginas_finales.append(nueva_pagina)

        if pos_pw_en_fb >= 0:
            fb_idx = pos_pw_en_fb + len(pag_pw["preguntas"])

    huerfanas_final = []
    for i in range(fb_idx, len(todas_fb)):
        key = todas_fb[i]["texto"].lower().strip()[:50]
        if key not in preguntas_pw_keys and todas_fb[i]["tipo"] != "informativo":
            huerfanas_final.append(todas_fb[i])

    if huerfanas_final:
        idx = max(0, len(paginas_finales) - 1)
        paginas_finales.insert(idx, {
            "numero": idx + 1,
            "preguntas": huerfanas_final,
            "botones": ["Siguiente"],
        })

    for i, pag in enumerate(paginas_finales):
        pag["numero"] = i + 1
    if paginas_finales:
        for pag in paginas_finales[:-1]:
            if "Enviar" in pag["botones"]:
                pag["botones"] = ["Siguiente"]
        paginas_finales[-1]["botones"] = ["Enviar"]

    resultado["paginas"] = paginas_finales
    resultado["total_preguntas"] = sum(len(p["preguntas"]) for p in paginas_finales)
    return resultado


def _combinar_resultados(principal, secundario):
    """Combina dos resultados, usando el principal como base."""
    textos_principal = set()
    for pag in principal["paginas"]:
        for preg in pag["preguntas"]:
            textos_principal.add(preg["texto"].lower().strip()[:50])

    preguntas_extra = []
    for pag in secundario["paginas"]:
        for preg in pag["preguntas"]:
            texto_norm = preg["texto"].lower().strip()[:50]
            if texto_norm not in textos_principal and preg["tipo"] != "informativo":
                preguntas_extra.append(preg)

    if preguntas_extra:
        print(f"    Combinando: {len(preguntas_extra)} preguntas extra del método secundario")
        if principal["paginas"]:
            idx = max(0, len(principal["paginas"]) - 1)
            nueva_pagina = {
                "numero": idx + 1,
                "preguntas": preguntas_extra,
                "botones": ["Siguiente"],
            }
            principal["paginas"].insert(idx, nueva_pagina)
            for i, pag in enumerate(principal["paginas"]):
                pag["numero"] = i + 1
            principal["paginas"][-1]["botones"] = ["Enviar"]
            principal["total_preguntas"] += len(preguntas_extra)

    if not principal["titulo"] and secundario["titulo"]:
        principal["titulo"] = secundario["titulo"]

    return principal


def _parsear_html_fallback(html, resultado):
    """Fallback: parsea el HTML directamente si FB_DATA no funciona."""
    print("  Usando parser HTML fallback...")

    titulo_match = re.search(r'<meta property="og:title" content="([^"]+)"', html)
    if titulo_match:
        resultado["titulo"] = titulo_match.group(1)

    desc_match = re.search(r'<meta property="og:description" content="([^"]+)"', html)
    if desc_match:
        resultado["descripcion"] = desc_match.group(1)

    preguntas = []
    params_matches = re.findall(r'data-params="([^"]+)"', html)
    for params in params_matches:
        try:
            decoded = params.replace("&quot;", '"').replace("&amp;", "&")
            data = json.loads(decoded)
            if isinstance(data, list) and len(data) > 1:
                texto = data[1] if len(data) > 1 else ""
                if texto and isinstance(texto, str):
                    preguntas.append({
                        "texto": texto,
                        "tipo": "desconocido",
                        "obligatoria": False,
                        "opciones": [],
                    })
        except Exception:
            pass

    if preguntas:
        resultado["paginas"] = [{
            "numero": 1,
            "preguntas": preguntas,
            "botones": ["Enviar"],
        }]
        resultado["total_preguntas"] = len(preguntas)

    return resultado


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://forms.gle/8gyKMyPr1BtYtHDE7"
    print(f"Scrapeando: {url}")
    resultado = scrape_formulario(url, headless=False)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))

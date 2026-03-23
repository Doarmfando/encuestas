"""
Estrategia de scraping: FB_PUBLIC_LOAD_DATA_ de Google Forms.
Extrae la variable JS que contiene toda la estructura del formulario.
"""
import re
import json

from app.constants.question_types import (
    GOOGLE_FORMS_TYPE_MAP,
    TIPO_SECCION, TIPO_IMAGEN, TIPO_ARCHIVO, TIPO_ESCALA_LINEAL,
    TIPO_MATRIZ, TIPO_MATRIZ_CHECKBOX, TIPO_TEXTO, TIPO_NUMERO,
)
from app.utils.question_inference import looks_numeric_question


class FBDataStrategy:
    """Extrae estructura de Google Forms desde FB_PUBLIC_LOAD_DATA_."""

    def extract(self, html: str, url: str = "") -> dict | None:
        """Intenta extraer la estructura del formulario desde FB_DATA.

        Returns:
            dict con estructura del formulario, o None si no se pudo extraer.
        """
        data = self._extraer_fb_data(html)
        if not data:
            return None

        print("  [FB_DATA] Variable encontrada, parseando...")
        resultado = {
            "url": url,
            "titulo": "",
            "descripcion": "",
            "paginas": [],
            "total_preguntas": 0,
            "requiere_login": False,
            "plataforma": "google_forms",
        }

        resultado = self._parsear_fb_data(data, resultado)
        print(f"    -> {resultado['total_preguntas']} preguntas en {len(resultado['paginas'])} páginas")
        return resultado if resultado["total_preguntas"] > 0 else None

    def _extraer_fb_data(self, html: str):
        """Extrae la variable FB_PUBLIC_LOAD_DATA_ del HTML."""
        try:
            match = re.search(
                r"FB_PUBLIC_LOAD_DATA_\s*=\s*(.+?);\s*</script>",
                html,
                re.DOTALL,
            )
            if match:
                return json.loads(match.group(1))
        except Exception as e:
            print(f"  Error extrayendo FB_DATA: {e}")
        return None

    def _parsear_fb_data(self, data, resultado):
        """Parsea la estructura de FB_PUBLIC_LOAD_DATA_."""
        try:
            resultado["titulo"] = data[1][0] if data[1] and data[1][0] else "Sin título"

            if data[1] and len(data[1]) > 1 and data[1][1]:
                resultado["descripcion"] = self._limpiar_html(str(data[1][1]))

            items = data[1][1] if len(data[1]) > 1 and isinstance(data[1][1], list) else []

            pagina_actual = {
                "numero": 1,
                "preguntas": [],
                "botones": ["Siguiente"],
            }

            for item in items:
                if not isinstance(item, list):
                    continue

                pregunta = self._parsear_item(item)

                if pregunta:
                    if pregunta["tipo"] == TIPO_SECCION:
                        if pagina_actual["preguntas"]:
                            resultado["paginas"].append(pagina_actual)
                            pagina_actual = {
                                "numero": len(resultado["paginas"]) + 1,
                                "preguntas": [],
                                "botones": ["Siguiente"],
                            }
                    else:
                        pagina_actual["preguntas"].append(pregunta)
                        resultado["total_preguntas"] += 1

            pagina_actual["botones"] = ["Enviar"]
            if pagina_actual["preguntas"]:
                resultado["paginas"].append(pagina_actual)

            if not resultado["paginas"] and resultado["total_preguntas"] == 0:
                resultado = self._intentar_parseo_alternativo(data, resultado)

        except Exception as e:
            print(f"  Error parseando FB_DATA: {e}")

        return resultado

    def _parsear_item(self, item):
        """Parsea un item individual de FB_PUBLIC_LOAD_DATA_."""
        try:
            titulo = item[1] if len(item) > 1 and item[1] else ""
            descripcion = item[2] if len(item) > 2 and item[2] else ""

            if len(item) <= 3 or item[3] is None:
                if titulo:
                    return {"tipo": "seccion", "texto": titulo, "opciones": [], "obligatoria": False}
                return None

            tipo_num = item[3] if len(item) > 3 else -1
            tipo = GOOGLE_FORMS_TYPE_MAP.get(tipo_num, "desconocido")

            # Tipos decorativos o no-respondibles: skip
            if tipo == TIPO_IMAGEN:
                return None

            pregunta = {
                "texto": titulo,
                "tipo": tipo,
                "obligatoria": False,
                "opciones": [],
            }

            if tipo == TIPO_TEXTO and looks_numeric_question(titulo, descripcion):
                pregunta["tipo"] = TIPO_NUMERO

            # Para archivo: marcar y no llenar
            if tipo == TIPO_ARCHIVO:
                pregunta["no_llenar"] = True
                return pregunta

            tiene_otro = False

            if len(item) > 4 and item[4] and isinstance(item[4], list):
                datos = item[4]
                for dato in datos:
                    if not isinstance(dato, list):
                        continue

                    # Obligatoria
                    if len(dato) > 2 and dato[2] == 1:
                        pregunta["obligatoria"] = True

                    # Detectar opción "Otro" (flag en posición 4 del dato)
                    if len(dato) > 4 and dato[4] == 1:
                        tiene_otro = True

                    # Extraer opciones
                    if len(dato) > 1 and isinstance(dato[1], list):
                        for opcion in dato[1]:
                            if isinstance(opcion, list) and len(opcion) > 0 and opcion[0]:
                                pregunta["opciones"].append(str(opcion[0]))

                    # Escala lineal: extraer labels de extremos
                    if tipo == TIPO_ESCALA_LINEAL and len(dato) > 1:
                        if isinstance(dato[1], list):
                            for opcion in dato[1]:
                                if isinstance(opcion, list) and len(opcion) > 0 and opcion[0]:
                                    if str(opcion[0]) not in pregunta["opciones"]:
                                        pregunta["opciones"].append(str(opcion[0]))
                        # Labels de extremos (ej: "Muy insatisfecho" - "Muy satisfecho")
                        if len(dato) > 3 and isinstance(dato[3], list):
                            labels = dato[3]
                            label_min = labels[0] if len(labels) > 0 and labels[0] else ""
                            label_max = labels[1] if len(labels) > 1 and labels[1] else ""
                            if label_min or label_max:
                                pregunta["etiquetas_escala"] = {
                                    "min": label_min,
                                    "max": label_max,
                                }

                    # Matriz / Grid: extraer filas y columnas
                    if tipo in (TIPO_MATRIZ, TIPO_MATRIZ_CHECKBOX) and len(dato) > 1:
                        # dato[1] = columnas (opciones de cada fila)
                        if isinstance(dato[1], list) and not pregunta["opciones"]:
                            for opcion in dato[1]:
                                if isinstance(opcion, list) and len(opcion) > 0 and opcion[0]:
                                    pregunta["opciones"].append(str(opcion[0]))

                # Extraer filas de la matriz (están en item[4][X][3] o en estructura paralela)
                if tipo in (TIPO_MATRIZ, TIPO_MATRIZ_CHECKBOX):
                    filas = self._extraer_filas_matriz(datos)
                    if filas:
                        pregunta["filas"] = filas

            if tiene_otro:
                pregunta["tiene_otro"] = True
                pregunta["opciones"].append("Otro")

            return pregunta

        except Exception as e:
            print(f"    Error parseando item: {e}")
            return None

    def _extraer_filas_matriz(self, datos):
        """Extrae las filas de una pregunta tipo matriz/grid."""
        filas = []
        for dato in datos:
            if not isinstance(dato, list):
                continue
            # Cada sub-item dentro de datos es una fila de la matriz
            # La estructura típica: [fila_id, columnas, obligatoria, ...]
            # donde fila_id es un número y el título está en dato[3][0] o dato[0]
            if len(dato) > 3 and isinstance(dato[3], list):
                for sub in dato[3]:
                    if isinstance(sub, list) and len(sub) > 0 and isinstance(sub[0], str):
                        if sub[0] not in filas:
                            filas.append(sub[0])
            # Alternativa: las filas están como strings directos
            if len(dato) > 0 and isinstance(dato[0], str) and dato[0] and len(dato[0]) > 1:
                if dato[0] not in filas:
                    filas.append(dato[0])
        # Si encontramos filas dentro de la estructura de FB_DATA
        # a veces están en item[4] como sublistas con [row_id, [[col_options]], required]
        if not filas:
            for dato in datos:
                if isinstance(dato, list) and len(dato) >= 2:
                    # Buscar el título de fila que es un string
                    for element in dato:
                        if isinstance(element, str) and len(element) > 1:
                            if element not in filas:
                                filas.append(element)
                            break
        return filas

    def _intentar_parseo_alternativo(self, data, resultado):
        """Intenta parsear con formato alternativo."""
        try:
            preguntas = []
            self._buscar_preguntas_recursivo(data, preguntas)

            if preguntas:
                resultado["paginas"] = [{
                    "numero": 1,
                    "preguntas": preguntas,
                    "botones": ["Enviar"],
                }]
                resultado["total_preguntas"] = len(preguntas)
        except Exception:
            pass
        return resultado

    def _buscar_preguntas_recursivo(self, data, preguntas, profundidad=0):
        """Busca preguntas recursivamente."""
        if profundidad > 8 or not isinstance(data, list):
            return

        if (len(data) >= 4
            and isinstance(data[1], str) and len(data[1]) > 2
            and isinstance(data[3], int) and data[3] in GOOGLE_FORMS_TYPE_MAP):
            pregunta = self._parsear_item(data)
            if pregunta and pregunta["tipo"] != TIPO_SECCION:
                preguntas.append(pregunta)
                return

        for item in data:
            if isinstance(item, list):
                self._buscar_preguntas_recursivo(item, preguntas, profundidad + 1)

    @staticmethod
    def _limpiar_html(texto: str) -> str:
        """Limpia tags HTML."""
        return re.sub(r"<[^>]+>", "", texto).strip()

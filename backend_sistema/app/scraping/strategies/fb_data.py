"""
Estrategia de scraping: FB_PUBLIC_LOAD_DATA_ de Google Forms.
Extrae la variable JS y normaliza multiples shapes internos al contrato canonico.
"""
import html as html_lib
import json
import re

from app.constants.question_types import (
    GOOGLE_FORMS_TYPE_MAP,
    TIPO_ARCHIVO,
    TIPO_ESCALA_LINEAL,
    TIPO_IMAGEN,
    TIPO_INFORMATIVO,
    TIPO_MATRIZ,
    TIPO_MATRIZ_CHECKBOX,
    TIPO_NUMERO,
    TIPO_SECCION,
    TIPO_TEXTO,
)
from app.utils.question_inference import looks_numeric_question


_WHITESPACE_RE = re.compile(r"\s+")
_SECTION_HEADING_RE = re.compile(r"^(secci[oó]n|secci.n|section|parte|bloque)\s+", re.IGNORECASE)


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

        resultado = self._parsear_fb_data(data, html, resultado)
        print(f"    -> {resultado['total_preguntas']} preguntas en {len(resultado['paginas'])} pÃ¡ginas")
        return resultado if resultado["total_preguntas"] > 0 else None

    def _extraer_fb_data(self, html: str):
        """Extrae la variable FB_PUBLIC_LOAD_DATA_ del HTML."""
        try:
            match = re.search(r"FB_PUBLIC_LOAD_DATA_\s*=\s*", html)
            if not match:
                return None
            decoder = json.JSONDecoder()
            payload_raw = html[match.end():].lstrip()
            data, _ = decoder.raw_decode(payload_raw)
            return data
        except Exception as e:
            print(f"  Error extrayendo FB_DATA: {e}")
        return None

    def _parsear_fb_data(self, data, html: str, resultado):
        """Parsea la estructura de FB_PUBLIC_LOAD_DATA_."""
        try:
            metadata = self._extraer_metadata(data)
            resultado["titulo"] = metadata["titulo"] or self._extraer_meta_html(html, "og:title") or "Sin tÃ­tulo"
            resultado["descripcion"] = metadata["descripcion"] or self._extraer_meta_html(html, "og:description")

            items = self._extraer_items(data)
            if items:
                resultado["paginas"] = self._normalizar_items(items)
                resultado["total_preguntas"] = sum(len(p["preguntas"]) for p in resultado["paginas"])

            if not resultado["paginas"] and resultado["total_preguntas"] == 0:
                resultado = self._intentar_parseo_alternativo(data, resultado)

        except Exception as e:
            print(f"  Error parseando FB_DATA: {e}")

        return resultado

    def _extraer_metadata(self, data) -> dict:
        """Obtiene titulo/descripcion usando el shape disponible del payload."""
        titulo = ""
        descripcion = ""

        root = data[1] if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list) else []
        if root:
            titulo = self._clean_text(root[0] if len(root) > 0 else "")
            for candidate in root[1:6]:
                if isinstance(candidate, str):
                    descripcion = self._clean_text(candidate)
                    if descripcion:
                        break

        return {"titulo": titulo, "descripcion": descripcion}

    def _extraer_items(self, data) -> list:
        """Ubica la lista de items del formulario aun cuando cambie el shape interno."""
        candidates = []

        def visit(node, depth=0):
            if depth > 6 or not isinstance(node, list):
                return
            score = self._score_items_list(node)
            if score > 0:
                candidates.append((score, len(node), node))
            for child in node:
                if isinstance(child, list):
                    visit(child, depth + 1)

        visit(data[1] if isinstance(data, list) and len(data) > 1 else data)
        if not candidates:
            return []
        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return candidates[0][2]

    def _score_items_list(self, value) -> int:
        if not isinstance(value, list):
            return 0
        return sum(1 for item in value if self._looks_like_form_item(item))

    @staticmethod
    def _looks_like_form_item(item) -> bool:
        return (
            isinstance(item, list)
            and len(item) > 3
            and isinstance(item[3], int)
            and item[3] in GOOGLE_FORMS_TYPE_MAP
        )

    def _normalizar_items(self, items: list) -> list:
        """Convierte la lista cruda de items al formato canonico del sistema."""
        paginas = []
        pagina_actual = self._nueva_pagina(1)
        pending_section_title = ""

        for item in items:
            if not self._looks_like_form_item(item):
                continue

            pregunta = self._parsear_item(item, pending_section_title=pending_section_title)
            if not pregunta:
                continue

            if pregunta["tipo"] == TIPO_SECCION:
                section_title = self._clean_text(pregunta.get("texto", ""))
                if pagina_actual["preguntas"]:
                    paginas.append(pagina_actual)
                    pagina_actual = self._nueva_pagina(len(paginas) + 1)
                if section_title:
                    pending_section_title = section_title
                continue

            if (
                pagina_actual["preguntas"]
                and not pending_section_title
                and self._looks_like_section_heading(pregunta.get("texto", ""))
            ):
                paginas.append(pagina_actual)
                pagina_actual = self._nueva_pagina(len(paginas) + 1)

            pregunta["texto"] = self._clean_text(pregunta.get("texto", "")) or pending_section_title
            if not pregunta["texto"]:
                continue

            pagina_actual["preguntas"].append(pregunta)
            pending_section_title = ""

        if pagina_actual["preguntas"]:
            paginas.append(pagina_actual)

        for idx, pagina in enumerate(paginas):
            pagina["numero"] = idx + 1
            pagina["botones"] = ["Enviar"] if idx == len(paginas) - 1 else ["Siguiente"]

        return paginas

    @staticmethod
    def _nueva_pagina(numero: int) -> dict:
        return {"numero": numero, "preguntas": [], "botones": ["Siguiente"]}

    def _parsear_item(self, item, pending_section_title: str = ""):
        """Parsea un item individual de FB_PUBLIC_LOAD_DATA_."""
        try:
            titulo = self._clean_text(item[1] if len(item) > 1 else "")
            descripcion = self._clean_text(item[2] if len(item) > 2 else "")
            contexto = self._extraer_contexto_item(item)

            if not titulo and descripcion and len(item) > 3 and item[3] is not None:
                titulo = descripcion
                descripcion = ""

            if len(item) <= 3 or item[3] is None:
                texto = titulo or descripcion or contexto or pending_section_title
                if texto:
                    return {"tipo": TIPO_SECCION, "texto": texto, "opciones": [], "obligatoria": False}
                return None

            tipo_num = item[3]
            tipo = GOOGLE_FORMS_TYPE_MAP.get(tipo_num, "desconocido")

            if tipo == TIPO_IMAGEN:
                return None

            if tipo == TIPO_SECCION:
                texto_seccion = titulo or contexto or descripcion or pending_section_title
                if not texto_seccion:
                    return None
                return {
                    "texto": texto_seccion,
                    "tipo": TIPO_SECCION,
                    "obligatoria": False,
                    "opciones": [],
                }

            if tipo == TIPO_INFORMATIVO:
                texto_info = titulo or descripcion or contexto
                if not texto_info:
                    return None
                return {
                    "texto": texto_info,
                    "tipo": TIPO_INFORMATIVO,
                    "obligatoria": False,
                    "opciones": [],
                }

            texto_pregunta = titulo or descripcion or pending_section_title or contexto
            pregunta = {
                "texto": texto_pregunta,
                "tipo": tipo,
                "obligatoria": False,
                "opciones": [],
            }

            if tipo == TIPO_TEXTO and looks_numeric_question(texto_pregunta, descripcion):
                pregunta["tipo"] = TIPO_NUMERO

            if tipo == TIPO_ARCHIVO:
                pregunta["no_llenar"] = True

            tiene_otro = False
            datos = item[4] if len(item) > 4 and isinstance(item[4], list) else []

            for dato in datos:
                if not isinstance(dato, list):
                    continue

                if len(dato) > 2 and dato[2] == 1:
                    pregunta["obligatoria"] = True

                if len(dato) > 4 and dato[4] == 1:
                    tiene_otro = True

                self._append_options_from_dato(pregunta, dato)

                if pregunta["tipo"] == TIPO_ESCALA_LINEAL:
                    self._append_scale_labels(pregunta, dato)

            if pregunta["tipo"] in (TIPO_MATRIZ, TIPO_MATRIZ_CHECKBOX):
                filas = self._extraer_filas_matriz(datos)
                if filas:
                    pregunta["filas"] = filas

            if tiene_otro:
                pregunta["tiene_otro"] = True
                self._append_unique(pregunta["opciones"], "Otro")

            if pregunta["tipo"] == TIPO_ARCHIVO and not pregunta["texto"]:
                pregunta["texto"] = pending_section_title

            return pregunta if pregunta["texto"] else None

        except Exception as e:
            print(f"    Error parseando item: {e}")
            return None

    def _append_options_from_dato(self, pregunta: dict, dato: list):
        if len(dato) <= 1 or not isinstance(dato[1], list):
            return
        for opcion in dato[1]:
            texto = self._extract_option_text(opcion)
            if texto:
                self._append_unique(pregunta["opciones"], texto)

    def _append_scale_labels(self, pregunta: dict, dato: list):
        if len(dato) <= 3 or not isinstance(dato[3], list):
            return
        labels = [self._clean_text(label) for label in dato[3] if isinstance(label, str)]
        labels = [label for label in labels if label]
        if len(labels) >= 2:
            pregunta["etiquetas_escala"] = {"min": labels[0], "max": labels[-1]}

    def _extraer_filas_matriz(self, datos):
        """Extrae las filas de una pregunta tipo matriz/grid."""
        filas = []
        for dato in datos:
            if not isinstance(dato, list):
                continue
            if len(dato) > 3:
                for fila in self._extract_row_texts(dato[3]):
                    self._append_unique(filas, fila)
            if len(dato) > 0 and isinstance(dato[0], str):
                self._append_unique(filas, self._clean_text(dato[0]))

        if filas:
            return filas

        for dato in datos:
            if not isinstance(dato, list):
                continue
            for element in dato:
                for fila in self._extract_row_texts(element):
                    self._append_unique(filas, fila)
                if filas:
                    break
            if filas:
                break
        return filas

    def _extract_row_texts(self, value) -> list:
        rows = []
        if isinstance(value, str):
            texto = self._clean_text(value)
            if texto:
                rows.append(texto)
            return rows

        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    texto = self._clean_text(item)
                    if texto:
                        rows.append(texto)
                elif isinstance(item, list):
                    nested = self._extract_row_texts(item)
                    if nested:
                        rows.extend(nested)
        return rows

    def _extract_option_text(self, opcion):
        if isinstance(opcion, str):
            return self._clean_text(opcion)
        if isinstance(opcion, list) and opcion:
            head = opcion[0]
            if isinstance(head, str):
                return self._clean_text(head)
        return ""

    def _extraer_contexto_item(self, item) -> str:
        """Busca texto auxiliar del item para sections/titulos heredados."""
        for idx in (11, 12, 13):
            if idx < 0 or idx >= len(item):
                continue
            for candidate in self._collect_strings(item[idx], max_depth=2):
                texto = self._clean_text(candidate)
                if texto:
                    return texto
        return ""

    def _collect_strings(self, value, max_depth: int = 3) -> list[str]:
        if max_depth < 0:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            resultado = []
            for item in value:
                resultado.extend(self._collect_strings(item, max_depth - 1))
            return resultado
        return []

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

        if self._looks_like_form_item(data):
            pregunta = self._parsear_item(data)
            if pregunta and pregunta["tipo"] != TIPO_SECCION:
                preguntas.append(pregunta)
                return

        for item in data:
            if isinstance(item, list):
                self._buscar_preguntas_recursivo(item, preguntas, profundidad + 1)

    @staticmethod
    def _extraer_meta_html(html: str, property_name: str) -> str:
        pattern = rf'<meta[^>]+property="{re.escape(property_name)}"[^>]+content="([^"]+)"'
        match = re.search(pattern, html, re.IGNORECASE)
        return FBDataStrategy._clean_text(match.group(1)) if match else ""

    @staticmethod
    def _append_unique(destino: list, valor: str):
        if valor and valor not in destino:
            destino.append(valor)

    @staticmethod
    def _looks_like_section_heading(texto: str) -> bool:
        normalized = FBDataStrategy._clean_text(texto).lower()
        return bool(_SECTION_HEADING_RE.match(normalized))

    @staticmethod
    def _clean_text(texto: str) -> str:
        if not texto:
            return ""
        texto = html_lib.unescape(str(texto))
        texto = re.sub(r"<[^>]+>", " ", texto)
        return _WHITESPACE_RE.sub(" ", texto).strip()

"""
Preparación del resumen de encuesta para enviar a la IA.
Solo responsabilidad: transformar la estructura scrapeada en un resumen compacto.
Para agregar un nuevo campo al resumen: editar solo este archivo.
"""
from app.constants.limits import MIN_PERFILES as _MIN_PERFILES, MAX_PERFILES as _MAX_PERFILES
from app.constants.limits import MIN_TENDENCIAS as _MIN_TENDENCIAS, MAX_TENDENCIAS as _MAX_TENDENCIAS
from app.constants.question_types import PATRONES_LIKERT

DEMOGRAPHIC_QUESTION_KEYWORDS = (
    "edad", "age", "sexo", "género", "genero", "gender", "ocupación", "ocupacion",
    "trabajo", "trabaja", "profesión", "profesion", "estudia", "estudiante",
    "estado civil", "casado", "soltero", "convive", "vive", "hijos", "embarazo",
    "educación", "educacion", "instrucción", "instruccion",
)


def es_escala(tipo: str, opciones: list | None = None) -> bool:
    """Determina si un tipo de pregunta es escala/Likert (incluye Likert disfrazado)."""
    if tipo == "matriz" or any(t in tipo.lower() for t in ("escala", "likert", "rating", "nps")):
        return True
    if tipo == "opcion_multiple" and opciones and len(opciones) >= 3:
        opciones_lower = {o.lower().strip() for o in opciones}
        for patron in PATRONES_LIKERT:
            if len(opciones_lower & patron) >= 3:
                return True
    return False


class SurveyPreparator:
    """Transforma la estructura scrapeada en un resumen compacto apto para IA.

    Para agregar un nuevo campo al resumen o cambiar cómo se detectan escalas,
    solo hay que modificar este archivo.
    """

    def preparar_resumen(self, estructura: dict) -> dict:
        """Retorna el resumen listo para serializar como JSON y enviar a la IA."""
        resumen: dict = {
            "titulo": estructura.get("titulo", ""),
            "descripcion": estructura.get("descripcion", ""),
            "preguntas": [],
            "preguntas_escala_likert": [],
            "limites_configuracion": {
                "perfiles": {"min": _MIN_PERFILES, "max": _MAX_PERFILES},
                "tendencias": {"min": _MIN_TENDENCIAS, "max": _MAX_TENDENCIAS},
            },
        }

        opciones_likert_vistas: set = set()

        for pagina in estructura.get("paginas", []):
            for pregunta in pagina.get("preguntas", []):
                tipo = pregunta.get("tipo", "")
                opciones = pregunta.get("opciones", [])
                if tipo in ("informativo", "desconocido", ""):
                    continue

                if es_escala(tipo, opciones):
                    opts_key = tuple(sorted(o.lower() for o in opciones))
                    opciones_likert_vistas.add(opts_key)
                    resumen["preguntas_escala_likert"].append({
                        "texto": pregunta["texto"],
                        "opciones": opciones,
                    })
                    continue

                entry: dict = {
                    "texto": pregunta["texto"],
                    "tipo": tipo,
                    "obligatoria": pregunta.get("obligatoria", False),
                }
                if opciones and len(opciones) <= 10:
                    entry["opciones"] = opciones
                elif opciones:
                    entry["opciones"] = opciones[:5] + [f"... (+{len(opciones)-5} más)"]
                resumen["preguntas"].append(entry)

        senales_demo = self._detectar_senales_demograficas(resumen["preguntas"])
        resumen["senales_demograficas_detectadas"] = senales_demo
        if not senales_demo:
            resumen["restriccion_perfiles"] = (
                "No hay preguntas demográficas explícitas. "
                "Los perfiles deben ser conductuales/actitudinales y no demográficos."
            )

        escalas = resumen["preguntas_escala_likert"]
        if escalas:
            primer_ejemplo = escalas[0]
            resumen["nota_escalas"] = (
                f"Hay {len(escalas)} preguntas de escala/Likert con opciones como "
                f"{primer_ejemplo['opciones']}. NO las incluyas en perfiles, "
                f"van en tendencias_escalas. Ejemplos: {', '.join(e['texto'][:40] for e in escalas[:3])}"
            )
        del resumen["preguntas_escala_likert"]

        return resumen

    def extraer_preguntas_referencia(self, estructura: dict) -> list:
        """Extrae lista plana de preguntas con tipo y opciones como referencia cruzada."""
        preguntas = []
        for pagina in estructura.get("paginas", []):
            for pregunta in pagina.get("preguntas", []):
                tipo = pregunta.get("tipo", "")
                if tipo in ("informativo", "desconocido", ""):
                    continue
                preguntas.append({
                    "texto": pregunta["texto"],
                    "tipo": tipo,
                    "opciones": pregunta.get("opciones", []),
                    "obligatoria": pregunta.get("obligatoria", False),
                })
        return preguntas

    def survey_supports_demographics(self, preguntas_ref: list) -> bool:
        """True si el formulario contiene al menos una pregunta demográfica explícita."""
        for pregunta in preguntas_ref:
            texto = str(pregunta.get("texto", "")).lower()
            if any(kw in texto for kw in DEMOGRAPHIC_QUESTION_KEYWORDS):
                return True
        return False

    def _detectar_senales_demograficas(self, preguntas: list) -> list:
        halladas = []
        for pregunta in preguntas:
            texto = str(pregunta.get("texto", "")).lower()
            for kw in DEMOGRAPHIC_QUESTION_KEYWORDS:
                if kw in texto and kw not in halladas:
                    halladas.append(kw)
        return halladas

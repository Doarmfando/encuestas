"""
Creación, validación y sanitización de perfiles.
Solo responsabilidad: garantizar que los perfiles existan, tengan el formato correcto
y no contengan supuestos demográficos inventados. Para cambiar la cantidad de perfiles
o sus nombres por defecto: solo editar este archivo.
"""
from app.services.analysis.survey_preparator import es_escala, DEMOGRAPHIC_QUESTION_KEYWORDS
from app.services.analysis.response_normalizer import ResponseNormalizer


MIN_PERFILES = 3
MAX_PERFILES = 4

SAFE_PROFILE_NAMES = [
    "Perfil conductual A",
    "Perfil conductual B",
    "Perfil conductual C",
    "Perfil conductual D",
]

UNSUPPORTED_PROFILE_KEYWORDS = (
    "ama de casa", "amas de casa", "joven", "adolescente", "adulto", "adulta",
    "hombre", "mujer", "madre", "padre", "mamá", "mama", "papá", "papa",
    "profesional", "independiente", "emprendedor", "emprendedora", "estudiante",
    "casado", "casada", "soltero", "soltera",
)


class ProfileManager:
    """Gestiona la cantidad y calidad de perfiles generados por la IA.

    Para agregar un nuevo nombre seguro de perfil o ampliar los límites,
    solo modificar las constantes de este archivo.
    """

    def __init__(self, normalizer: ResponseNormalizer):
        self._normalizer = normalizer

    def asegurar_cantidad(self, perfiles: list, preguntas_ref: list) -> list:
        """Garantiza entre MIN y MAX perfiles, completando con defaults si falta."""
        perfiles = list(perfiles or [])[:MAX_PERFILES]
        if len(perfiles) >= MIN_PERFILES:
            return perfiles

        faltantes = MIN_PERFILES - len(perfiles)
        perfiles.extend(self._crear_defaults(preguntas_ref, faltantes, offset=len(perfiles)))
        return perfiles[:MAX_PERFILES]

    def sanitizar_no_soportados(self, perfiles: list, preguntas_ref: list):
        """Reemplaza nombres de perfiles demográficos inventados por nombres seguros."""
        if self._survey_supports_demographics(preguntas_ref):
            return

        replacement_idx = 0
        for perfil in perfiles:
            texto = f"{perfil.get('nombre', '')} {perfil.get('descripcion', '')}".lower()
            if any(kw in texto for kw in UNSUPPORTED_PROFILE_KEYWORDS):
                safe_name = SAFE_PROFILE_NAMES[min(replacement_idx, len(SAFE_PROFILE_NAMES) - 1)]
                perfil["nombre"] = safe_name
                perfil["descripcion"] = (
                    "Perfil conductual derivado de patrones de respuesta del formulario, "
                    "sin asumir edad, sexo, ocupación u otros rasgos no preguntados."
                )
                replacement_idx += 1

    def crear_defaults(self, preguntas_ref: list, cantidad: int, offset: int = 0) -> list:
        return self._crear_defaults(preguntas_ref, cantidad, offset)

    # ── privados ──────────────────────────────────────────────────────────────

    def _crear_defaults(self, preguntas_ref: list, cantidad: int, offset: int) -> list:
        perfiles = []
        frecuencias_base = [40, 35, 25, 20]
        for idx in range(cantidad):
            nombre_idx = min(offset + idx, len(SAFE_PROFILE_NAMES) - 1)
            perfil = {
                "nombre": SAFE_PROFILE_NAMES[nombre_idx],
                "descripcion": (
                    "Perfil basado en patrones observables del formulario, "
                    "sin asumir rasgos demográficos no preguntados."
                ),
                "frecuencia": frecuencias_base[min(offset + idx, len(frecuencias_base) - 1)],
                "respuestas": {},
            }
            for ref in preguntas_ref:
                if not es_escala(ref["tipo"], ref.get("opciones", [])):
                    perfil["respuestas"][ref["texto"]] = self._normalizer.generar_respuesta_default(ref)
            perfiles.append(perfil)
        return perfiles

    def _survey_supports_demographics(self, preguntas_ref: list) -> bool:
        for pregunta in preguntas_ref:
            texto = str(pregunta.get("texto", "")).lower()
            if any(kw in texto for kw in DEMOGRAPHIC_QUESTION_KEYWORDS):
                return True
        return False

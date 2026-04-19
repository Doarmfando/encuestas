"""
Orquestador de generación de respuestas.

Solo coordina el flujo: elegir perfil → elegir tendencia → generar → aplicar reglas → garantizar.
Para cambiar el comportamiento de cualquier paso, editar el submódulo correspondiente
en app/services/generation/ sin tocar este archivo.
"""
from app.services.generation.profile_selector import ProfileSelector
from app.services.generation.response_generator import ResponseGenerator
from app.services.generation.rules_engine import RulesEngine


class GeneratorService:
    """Genera respuestas coherentes basadas en configuración de perfiles."""

    def __init__(self):
        self._selector = ProfileSelector()
        self._generator = ResponseGenerator()
        self._rules = RulesEngine()

    def generate(self, configuracion: dict, estructura_encuesta: dict) -> dict:
        """Genera una respuesta completa para el formulario."""
        perfiles = configuracion.get("perfiles", [])
        reglas = configuracion.get("reglas_dependencia", [])
        tendencias = configuracion.get("tendencias_escalas", [])

        perfil = self._selector.elegir_perfil(perfiles)
        tendencia = self._selector.elegir_tendencia(tendencias, perfil)

        respuesta = self._generator.generar(perfil, estructura_encuesta, tendencia)
        respuesta = self._rules.aplicar(respuesta, reglas)
        respuesta = self._generator.garantizar_obligatorias(respuesta, estructura_encuesta)

        respuesta["_perfil"] = perfil.get("nombre", "desconocido")
        respuesta["_tendencia"] = tendencia.get("nombre", "desconocido")
        return respuesta

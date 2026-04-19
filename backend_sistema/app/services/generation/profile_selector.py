"""
Selección aleatoria ponderada de perfiles y tendencias.
Solo responsabilidad: elegir qué perfil y tendencia usar en cada generación.
Para cambiar la lógica de selección (ej. round-robin en vez de ponderado): solo editar aquí.
"""
import random
from app.utils.fuzzy_matcher import find_best_match


class ProfileSelector:
    """Selecciona perfil y tendencia para una generación de respuesta.

    Para agregar un nuevo modo de selección (ej. secuencial, balanceado),
    agregar un método `elegir_*` y llamarlo desde GeneratorService. Nada más cambia.
    """

    def elegir_perfil(self, perfiles: list) -> dict:
        """Selección ponderada por frecuencia."""
        if not perfiles:
            return {"nombre": "default", "respuestas": {}, "frecuencia": 100}
        pesos = [p.get("frecuencia", 10) for p in perfiles]
        return random.choices(perfiles, weights=pesos)[0]

    def elegir_tendencia(self, tendencias: list, perfil: dict | None = None) -> dict:
        """Selección ponderada, sesgada por preferencias del perfil si existen."""
        if not tendencias:
            return {"nombre": "neutro", "distribuciones": {"5": [20, 20, 20, 20, 20]}, "frecuencia": 100}

        pesos = [t.get("frecuencia", 10) for t in tendencias]
        if perfil:
            preferencias = self._preferencias_del_perfil(perfil, tendencias)
            if preferencias:
                pesos = [peso * preferencias.get(t.get("nombre", ""), 1) for peso, t in zip(pesos, tendencias)]

        return random.choices(tendencias, weights=pesos)[0]

    # ── privados ──────────────────────────────────────────────────────────────

    def _preferencias_del_perfil(self, perfil: dict, tendencias: list) -> dict:
        nombres = [t.get("nombre", "") for t in tendencias if t.get("nombre")]
        preferencias = {n: 1.0 for n in nombres}

        sugerida = find_best_match(perfil.get("tendencia_sugerida") or "", nombres, threshold=0.7)
        if sugerida:
            preferencias[sugerida] = max(preferencias[sugerida], 4.0)

        preferidas = perfil.get("tendencias_preferidas", {})
        if isinstance(preferidas, dict):
            for nombre, peso in preferidas.items():
                match = find_best_match(nombre, nombres, threshold=0.7)
                if not match:
                    continue
                try:
                    preferencias[match] = max(preferencias[match], max(1.0, float(peso) / 25))
                except Exception:
                    preferencias[match] = max(preferencias[match], 2.0)

        return preferencias

"""
Gestión de tendencias de escala Likert y sus distribuciones.
Solo responsabilidad: crear, corregir y normalizar tendencias.
Para agregar una nueva distribución predefinida (ej. 'bimodal'): solo editar aquí.
"""
from app.constants.limits import MIN_TENDENCIAS, MAX_TENDENCIAS
from app.services.analysis.response_normalizer import ajustar_suma_exacta


class TendencyManager:
    """Gestiona tendencias de escala Likert.

    Para agregar un nuevo tipo de distribución de respuestas (ej. distribución bimodal),
    agregar el método _dist_* y referenciarlo en _crear_defaults, sin tocar el orquestador.
    """

    def corregir(self, resultado: dict, tiene_escalas: bool, tamaños: set):
        """Corrige el campo tendencias_escalas del resultado de la IA."""
        tendencias = resultado.get("tendencias_escalas", [])
        tamaños_objetivo = set(tamaños or set()) or {5, 7, 11}

        for tendencia in tendencias:
            if "distribucion" in tendencia and "distribuciones" not in tendencia:
                dist = tendencia.pop("distribucion")
                if isinstance(dist, list):
                    tendencia["distribuciones"] = {str(len(dist)): dist}

            tendencia.setdefault("distribuciones", {})

            for tam in tamaños_objetivo:
                tam_str = str(tam)
                if tam_str not in tendencia["distribuciones"]:
                    tendencia["distribuciones"][tam_str] = self._dist_centrada(tam)

            for tam_str, dist in tendencia["distribuciones"].items():
                total = sum(dist)
                if total > 0 and total != 100:
                    tendencia["distribuciones"][tam_str] = ajustar_suma_exacta(dist)

        if not tendencias:
            resultado["tendencias_escalas"] = self.crear_defaults(tamaños_objetivo)

    def asegurar_cantidad(self, tendencias: list, tamaños: set) -> list:
        """Garantiza entre MIN y MAX tendencias."""
        tendencias = list(tendencias or [])[:MAX_TENDENCIAS]
        if len(tendencias) >= MIN_TENDENCIAS:
            return tendencias

        existentes = {t.get("nombre", "") for t in tendencias}
        for default in self.crear_defaults(tamaños):
            if default["nombre"] not in existentes:
                tendencias.append(default)
                existentes.add(default["nombre"])
            if len(tendencias) >= MIN_TENDENCIAS:
                break
        return tendencias[:MAX_TENDENCIAS]

    def crear_defaults(self, tamaños: set | None = None) -> list:
        """Crea las 3 tendencias genéricas para cuando la IA no las proporciona."""
        tamaños_escala = set(tamaños or set()) or {5, 7, 11}
        dist_medio = {str(t): self._dist_centrada(t) for t in tamaños_escala}
        dist_alto = {str(t): self._dist_sesgada_alta(t) for t in tamaños_escala}
        dist_bajo = {str(t): self._dist_sesgada_baja(t) for t in tamaños_escala}
        return [
            {"nombre": "Término Medio", "descripcion": "Responde en valores centrales y estables.", "frecuencia": 40, "distribuciones": dist_medio},
            {"nombre": "Centro-Alto", "descripcion": "Tiende a responder ligeramente por encima del centro.", "frecuencia": 30, "distribuciones": dist_alto},
            {"nombre": "Centro-Bajo", "descripcion": "Tiende a responder ligeramente por debajo del centro.", "frecuencia": 30, "distribuciones": dist_bajo},
        ]

    # ── distribuciones base ────────────────────────────────────────────────────

    def _dist_centrada(self, tam: int) -> list:
        centro = (tam - 1) / 2
        dist = [max(1, round(40 * (1 / (1 + abs(i - centro))))) for i in range(tam)]
        return ajustar_suma_exacta(dist)

    def _dist_sesgada_alta(self, tam: int) -> list:
        centro = (tam - 1) * 0.6
        dist = [max(1, round(40 * (1 / (1 + abs(i - centro))))) for i in range(tam)]
        return ajustar_suma_exacta(dist)

    def _dist_sesgada_baja(self, tam: int) -> list:
        centro = (tam - 1) * 0.4
        dist = [max(1, round(40 * (1 / (1 + abs(i - centro))))) for i in range(tam)]
        return ajustar_suma_exacta(dist)

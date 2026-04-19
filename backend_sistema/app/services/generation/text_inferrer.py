"""
Inferencia de valores de texto libre según el enunciado de la pregunta.
Solo responsabilidad: dado el texto de una pregunta, devolver un valor plausible.
Para agregar soporte a un nuevo patrón (ej. 'código de trabajador'): solo editar aquí.
"""
import random
import re

_NOMBRES_COMPLETOS = [
    "Juan Pérez", "María García", "Carlos López", "Ana Torres", "Luis Mendoza",
    "Rosa Quispe", "Pedro Huamán", "Carmen Flores", "José Rojas", "Elena Vargas",
]
_NOMBRES_SIMPLES = ["Juan", "María", "Carlos", "Ana", "Luis", "Rosa", "Pedro", "Carmen", "José", "Elena"]

_PATRONES: list[tuple[re.Pattern, callable]] = [
    (re.compile(r'\bedad\b|\bage\b|\baños\b'),
     lambda: str(random.randint(20, 55))),
    (re.compile(r'\bdni\b|\bdocumento\b|\bcédula\b|\bcedula\b'),
     lambda: str(random.randint(10_000_000, 99_999_999))),
    (re.compile(r'\btel[eé]fono\b|\bcelular\b|\bmóvil\b|\bmovil\b|\bphone\b'),
     lambda: f"9{random.randint(10_000_000, 99_999_999)}"),
    (re.compile(r'\bc[oó]digo postal\b|\bzip\b'),
     lambda: str(random.randint(10_000, 99_999))),
    (re.compile(r'\baño\b|\byear\b'),
     lambda: str(random.randint(2015, 2025))),
    (re.compile(r'\bn[uú]mero\b|\bcuántos\b|\bcuantos\b|\bcantidad\b'),
     lambda: str(random.randint(1, 20))),
    (re.compile(r'\bemail\b|\bcorreo\b|\be-mail\b'),
     lambda: f"usuario{random.randint(100, 999)}@gmail.com"),
    (re.compile(r'\bnombre completo\b|\bnombre y apellido\b|\bfull name\b'),
     lambda: random.choice(_NOMBRES_COMPLETOS)),
    (re.compile(r'\bnombre\b|\bname\b'),
     lambda: random.choice(_NOMBRES_SIMPLES)),
]


def infer_text_value(texto_pregunta: str) -> str:
    """Infiere un valor de texto plausible para la pregunta dada.

    Para agregar un nuevo patrón, agregar una tupla (re.compile(...), lambda) a _PATRONES.
    No hay que tocar ningún otro archivo.
    """
    t = texto_pregunta.lower().strip()
    for patron, generador in _PATRONES:
        if patron.search(t):
            return generador()
    return "respuesta"

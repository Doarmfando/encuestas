"""
Analizador de encuestas con GPT.
Recibe la estructura scrapeada y genera perfiles + reglas + tendencias.
"""
import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

PROMPT_SISTEMA = """Eres un experto en metodología de investigación y psicometría.
Tu trabajo es analizar encuestas y generar perfiles demográficos realistas y coherentes
para simular respuestas humanas variadas.

REGLAS IMPORTANTES:
- Los perfiles deben ser coherentes internamente (edad-ocupación-estado civil-hijos deben tener sentido)
- Las tendencias de respuesta en escalas deben reflejar personalidades reales
- Incluir reglas de dependencia entre preguntas (ej: ama de casa solo para mujeres)
- Los pesos/probabilidades deben sumar 100 en cada distribución
- Generar variedad: no todos los perfiles deben ser positivos o similares
- Para campos de texto numérico (como edad), usar rangos min/max
- Para campos de texto libre, dar ejemplos de respuestas variadas

SIEMPRE responde en JSON válido, sin markdown, sin comentarios."""

PROMPT_ANALISIS = """Analiza esta encuesta scrapeada y genera una configuración completa.

ENCUESTA:
{encuesta_json}

Genera un JSON con esta estructura EXACTA:
{{
  "perfiles": [
    {{
      "nombre": "nombre descriptivo del perfil",
      "descripcion": "breve descripción de quién es esta persona",
      "frecuencia": 25,
      "respuestas": {{
        "Texto exacto de la pregunta": {{
          "tipo": "fijo|aleatorio|rango",
          "valor": "valor fijo si tipo=fijo",
          "opciones": {{"opcion1": 60, "opcion2": 40}},
          "min": 18,
          "max": 25
        }}
      }}
    }}
  ],
  "reglas_dependencia": [
    {{
      "si_pregunta": "Texto de la pregunta condición",
      "si_valor": "valor que activa la regla",
      "operador": "igual|diferente|menor|mayor",
      "entonces_pregunta": "Texto de la pregunta afectada",
      "entonces_excluir": ["opciones que NO pueden aparecer"],
      "entonces_forzar": "valor forzado (opcional, null si no aplica)"
    }}
  ],
  "tendencias_escalas": [
    {{
      "nombre": "nombre de la tendencia (ej: optimista, neutro, pesimista)",
      "descripcion": "descripción de cómo responde esta persona",
      "frecuencia": 30,
      "distribucion": [5, 10, 25, 35, 25]
    }}
  ]
}}

INSTRUCCIONES:
- Genera entre 4 y 8 perfiles demográficos variados y coherentes
- Genera entre 3 y 6 tendencias para las escalas
- Las frecuencias de perfiles deben sumar 100
- Las frecuencias de tendencias deben sumar 100
- Las reglas deben reflejar coherencia del mundo real
- Para preguntas de escala/likert, NO las incluyas en los perfiles, solo en tendencias_escalas
- Para preguntas informativas (sin respuesta), ignóralas
- Asegúrate de que el JSON sea válido"""


def analizar_encuesta(estructura_scrapeada):
    """Envía la estructura scrapeada a GPT y recibe perfiles + reglas."""

    # Preparar resumen de la encuesta para GPT
    resumen = _preparar_resumen(estructura_scrapeada)

    print("  Enviando a GPT para análisis...")

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": PROMPT_SISTEMA},
                {"role": "user", "content": PROMPT_ANALISIS.format(encuesta_json=json.dumps(resumen, ensure_ascii=False, indent=2))},
            ],
            temperature=0.7,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )

        contenido = response.choices[0].message.content
        resultado = json.loads(contenido)

        # Validar estructura
        resultado = _validar_resultado(resultado)

        print(f"  GPT generó:")
        print(f"    {len(resultado.get('perfiles', []))} perfiles")
        print(f"    {len(resultado.get('reglas_dependencia', []))} reglas")
        print(f"    {len(resultado.get('tendencias_escalas', []))} tendencias")

        return resultado

    except Exception as e:
        print(f"  Error con GPT: {e}")
        return _generar_fallback(estructura_scrapeada)


def _preparar_resumen(estructura):
    """Prepara un resumen limpio de la encuesta para enviar a GPT."""
    resumen = {
        "titulo": estructura.get("titulo", ""),
        "descripcion": estructura.get("descripcion", ""),
        "preguntas": [],
    }

    for pagina in estructura.get("paginas", []):
        for pregunta in pagina.get("preguntas", []):
            if pregunta["tipo"] != "informativo":
                resumen["preguntas"].append({
                    "texto": pregunta["texto"],
                    "tipo": pregunta["tipo"],
                    "obligatoria": pregunta["obligatoria"],
                    "opciones": pregunta["opciones"],
                })

    return resumen


def _validar_resultado(resultado):
    """Valida y corrige la estructura del resultado de GPT."""
    if "perfiles" not in resultado:
        resultado["perfiles"] = []
    if "reglas_dependencia" not in resultado:
        resultado["reglas_dependencia"] = []
    if "tendencias_escalas" not in resultado:
        resultado["tendencias_escalas"] = []

    # Validar que las frecuencias de perfiles sumen 100
    total_perfiles = sum(p.get("frecuencia", 0) for p in resultado["perfiles"])
    if total_perfiles > 0 and total_perfiles != 100:
        factor = 100 / total_perfiles
        for p in resultado["perfiles"]:
            p["frecuencia"] = round(p.get("frecuencia", 0) * factor)

    # Validar que las frecuencias de tendencias sumen 100
    total_tendencias = sum(t.get("frecuencia", 0) for t in resultado["tendencias_escalas"])
    if total_tendencias > 0 and total_tendencias != 100:
        factor = 100 / total_tendencias
        for t in resultado["tendencias_escalas"]:
            t["frecuencia"] = round(t.get("frecuencia", 0) * factor)

    return resultado


def _generar_fallback(estructura):
    """Genera una configuración básica si GPT falla."""
    print("  Usando configuración fallback (sin GPT)")

    preguntas = []
    for pagina in estructura.get("paginas", []):
        for pregunta in pagina.get("preguntas", []):
            if pregunta["tipo"] != "informativo":
                preguntas.append(pregunta)

    perfil_base = {
        "nombre": "General",
        "descripcion": "Perfil genérico con respuestas aleatorias",
        "frecuencia": 100,
        "respuestas": {},
    }

    for pregunta in preguntas:
        if pregunta["tipo"] == "opcion_multiple" and pregunta["opciones"]:
            peso = round(100 / len(pregunta["opciones"]))
            perfil_base["respuestas"][pregunta["texto"]] = {
                "tipo": "aleatorio",
                "opciones": {op: peso for op in pregunta["opciones"]},
            }
        elif pregunta["tipo"] == "numero":
            perfil_base["respuestas"][pregunta["texto"]] = {
                "tipo": "rango",
                "min": 18,
                "max": 60,
            }
        elif pregunta["tipo"] == "texto":
            perfil_base["respuestas"][pregunta["texto"]] = {
                "tipo": "fijo",
                "valor": "Sin respuesta",
            }

    return {
        "perfiles": [perfil_base],
        "reglas_dependencia": [],
        "tendencias_escalas": [
            {
                "nombre": "Neutro",
                "descripcion": "Respuestas balanceadas",
                "frecuencia": 100,
                "distribucion": [10, 20, 40, 20, 10],
            }
        ],
    }


if __name__ == "__main__":
    # Test rápido
    test = {
        "titulo": "Test",
        "paginas": [
            {
                "preguntas": [
                    {"texto": "Sexo", "tipo": "opcion_multiple", "obligatoria": True, "opciones": ["Hombre", "Mujer"]},
                    {"texto": "Edad", "tipo": "numero", "obligatoria": True, "opciones": []},
                ]
            }
        ],
    }
    resultado = analizar_encuesta(test)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))

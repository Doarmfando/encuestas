"""
Prompts centralizados para todas las operaciones de IA.
"""

# ============ ANÁLISIS DE ENCUESTAS ============

TIPOS_RESPUESTA_PERMITIDOS = """TIPOS PERMITIDOS (solo estos 3):
- "fijo": {"tipo": "fijo", "valor": "respuesta exacta"}
- "aleatorio": {"tipo": "aleatorio", "opciones": {"texto exacto": 60, "otro texto": 40}}
- "rango": {"tipo": "rango", "min": 18, "max": 35}

REGLAS DEL FORMATO:
- Nunca uses otros tipos.
- En "aleatorio", "opciones" debe ser un objeto y sumar 100.
- En "fijo", usa "valor".
- En "rango", usa "min" y "max".
- No uses null como respuesta final de una pregunta.
- Si una pregunta es condicional, resuélvela con reglas_dependencia."""

TIPOS_RESPUESTA_PERMITIDOS_TEMPLATE = (
    TIPOS_RESPUESTA_PERMITIDOS.replace("{", "{{").replace("}", "}}")
)

PROMPT_SISTEMA_ANALISIS = f"""Eres un experto en metodología de investigación, psicometría y simulación de respuestas humanas.
Analizas encuestas y devuelves configuraciones realistas, consistentes y reutilizables.

{TIPOS_RESPUESTA_PERMITIDOS}

REGLAS DURAS:
- Usa el texto exacto de preguntas y opciones cuando existan opciones visibles.
- No inventes demografía ni roles sociales si el formulario no los sustenta.
- Las preguntas de escala, likert, matriz o nps no van dentro de respuestas de perfiles; van en tendencias_escalas.
- Devuelve solo JSON válido, sin markdown, sin comentarios y sin texto extra."""

PROMPT_ANALISIS_ENCUESTA = """Analiza esta encuesta y genera una configuración completa para simular respuestas humanas.

ENCUESTA SCRAPEADA:
{encuesta_json}

Devuelve solo un JSON válido con esta estructura mínima:
{{
  "perfiles": [
    {{
      "nombre": "Nombre descriptivo del perfil",
      "descripcion": "Contexto breve y realista",
      "frecuencia": 25,
      "tendencia_sugerida": "Nombre de tendencia o null",
      "reglas_coherencia": ["Regla breve 1", "Regla breve 2"],
      "respuestas": {{
        "Texto exacto de la pregunta": {{
          "tipo": "fijo|aleatorio|rango"
        }}
      }}
    }}
  ],
  "reglas_dependencia": [
    {{
      "si_pregunta": "Texto exacto",
      "si_valor": "valor gatillo",
      "operador": "igual|diferente|menor|mayor",
      "entonces_pregunta": "Texto exacto",
      "entonces_excluir": ["opción exacta"],
      "entonces_forzar": null
    }}
  ],
  "tendencias_escalas": [
    {{
      "nombre": "Nombre de tendencia",
      "descripcion": "Descripción breve",
      "frecuencia": 34,
      "distribuciones": {{
        "5": [5, 20, 50, 20, 5]
      }}
    }}
  ]
}}

INSTRUCCIONES:
1. Respeta los límites del resumen: genera entre 3 y 4 perfiles y entre 3 y 4 tendencias. Las frecuencias de cada bloque deben sumar exactamente 100.
2. Cada perfil debe incluir todas las preguntas respondibles que no sean informativas ni de escala.
3. Copia exactamente el texto de preguntas y opciones. No traduzcas, no corrijas y no inventes opciones.
4. Si el resumen indica que no hay demografía explícita, usa perfiles conductuales o actitudinales. No uses etiquetas como "ama de casa", "joven emprendedor" o similares.
5. Si sí hay demografía explícita, úsala solo cuando esté respaldada por preguntas reales del formulario.
6. Cada perfil debe tener descripción breve, 2 a 5 reglas_coherencia y una tendencia_sugerida reutilizable cuando existan tendencias.
7. Crea reglas_dependencia solo cuando una respuesta habilita, excluye o fuerza otra respuesta.
8. Para escalas:
   - Nunca las pongas dentro de respuestas del perfil.
   - Usa "distribuciones", no "distribucion".
   - Incluye una distribución para cada tamaño de escala detectado.
   - Si no hay escalas, igual devuelve 3 tendencias genéricas reutilizables con tamaños "5", "7" y "11".
9. Usa estos criterios por tipo de pregunta:
   - opcion_multiple, seleccion_multiple, desplegable: "aleatorio" con opciones exactas.
   - texto: "aleatorio" con mínimo 4 variantes realistas.
   - parrafo: "aleatorio" con mínimo 3 variantes de 2 a 4 oraciones.
   - numero: "rango" coherente con el perfil.
   - fecha: "rango" expresado como números.
   - hora: "aleatorio" con formato "HH:MM".
   - matriz_checkbox: "aleatorio" con combinaciones válidas.
   - ranking: "aleatorio" con órdenes posibles como texto.
   - archivo, informativo, desconocido, imagen: ignóralos.

""" + TIPOS_RESPUESTA_PERMITIDOS_TEMPLATE + """

Antes de responder, verifica:
- perfiles entre 3 y 4
- tendencias entre 3 y 4
- probabilidades internas en 100
- frecuencias globales en 100
- JSON válido sin comentarios"""


# ============ SCRAPING GENÉRICO CON IA ============

PROMPT_SISTEMA_SCRAPING = """Eres un experto en web scraping y análisis de formularios web.
Tu trabajo es analizar formularios públicos de Google Forms o Microsoft Forms y extraer su estructura.
Si la página no corresponde claramente a una de esas dos plataformas, marca la plataforma como "unsupported".

SIEMPRE responde en JSON válido, sin markdown, sin comentarios."""

PROMPT_ANALIZAR_HTML = """Analiza este HTML de una página de encuesta/formulario y extrae su estructura.

HTML (puede estar truncado):
{html_content}

URL: {url}

Extrae un JSON con esta estructura EXACTA:
{{
  "titulo": "título de la encuesta",
  "descripcion": "descripción si existe",
  "paginas": [
    {{
      "numero": 1,
      "preguntas": [
        {{
          "texto": "texto de la pregunta",
          "tipo": "ver tipos abajo",
          "obligatoria": true,
          "opciones": ["opcion1", "opcion2"],
          "filas": ["fila1", "fila2"],
          "tiene_otro": false
        }}
      ],
      "botones": ["Siguiente"] o ["Enviar"]
    }}
  ],
  "total_preguntas": 5,
  "plataforma_detectada": "google_forms|microsoft_forms|unsupported"
}}

TIPOS DE PREGUNTA SOPORTADOS:
- "texto": Campo de texto corto
- "parrafo": Campo de texto largo (textarea)
- "numero": Campo numérico
- "opcion_multiple": Radio buttons (una sola opción)
- "seleccion_multiple": Checkboxes (múltiples opciones)
- "escala_lineal": Escala numérica (1-5, 1-7, 1-10, etc.)
- "nps": Net Promoter Score (0-10)
- "desplegable": Lista desplegable / dropdown / select
- "fecha": Selector de fecha
- "hora": Selector de hora
- "matriz": Grid de radio buttons (filas x columnas). Incluir "filas" y "opciones" (columnas)
- "matriz_checkbox": Grid de checkboxes (filas x columnas). Incluir "filas" y "opciones"
- "likert": Matriz tipo Likert (filas con escalas). Incluir "filas" y "opciones"
- "ranking": Ordenar opciones por preferencia. Las opciones son los items a ordenar
- "archivo": Subir archivo (marcar como no_llenar: true)
- "informativo": Texto informativo sin respuesta

CAMPOS ESPECIALES:
- "filas": SOLO para matriz/likert/matriz_checkbox. Lista de textos de cada fila
- "tiene_otro": true si la pregunta tiene opción "Otro" con campo de texto libre
- "no_llenar": true para preguntas que no se pueden automatizar (archivo)
- "etiquetas_escala": {{"min": "etiqueta baja", "max": "etiqueta alta"}} para escalas

INSTRUCCIONES:
- Identifica TODAS las preguntas del formulario
- Clasifica el tipo correctamente usando los tipos de arriba
- Extrae todas las opciones disponibles
- Para matrices/likert: extrae tanto filas como columnas (opciones)
- Detecta si las preguntas son obligatorias
- Si detectas múltiples páginas/secciones, sepáralas
- La última página debe tener botón "Enviar", las intermedias "Siguiente"
- Solo devuelve "google_forms" o "microsoft_forms" cuando la evidencia visual/HTML sea clara; si no, usa "unsupported"
"""


# ============ NAVEGACIÓN CON IA ============

PROMPT_SISTEMA_NAVEGACION = """Eres un experto en automatización web.
Analizas capturas de pantalla o HTML de páginas web para identificar elementos interactivos.

SIEMPRE responde en JSON válido."""

PROMPT_DETECTAR_BOTONES = """Analiza este HTML y encuentra los botones de navegación del formulario.

HTML:
{html_content}

Busca botones para: avanzar (siguiente/next), enviar (submit), retroceder (back).

Responde con JSON:
{{
  "botones": [
    {{
      "tipo": "siguiente|enviar|atras",
      "selector_css": "selector CSS para encontrarlo",
      "texto": "texto visible del botón",
      "confianza": 0.95
    }}
  ]
}}"""

PROMPT_DETECTAR_CAMPOS = """Analiza este HTML y encuentra los campos del formulario para la pregunta dada.

HTML del contenedor de la pregunta:
{html_content}

Pregunta: {pregunta}
Tipo esperado: {tipo}
Valor a ingresar: {valor}

Responde con JSON:
{{
  "selector_css": "selector CSS del campo/opción a interactuar",
  "accion": "click|fill|select",
  "valor_para_accion": "valor si es fill/select",
  "confianza": 0.9
}}"""


# ============ GENERACIÓN DE PERFILES PERSONALIZADOS ============

PROMPT_GENERAR_PERFIL = """Genera un perfil detallado basado en estos parámetros:

Contexto de la encuesta: {contexto}
Restricciones del usuario: {restricciones}

""" + TIPOS_RESPUESTA_PERMITIDOS_TEMPLATE + """

Genera un JSON con:
{{
  "nombre": "nombre descriptivo",
  "descripcion": "descripción detallada de la persona",
  "frecuencia": 25,
  "respuestas": {{
    "texto exacto de la pregunta": {{
      "tipo": "fijo|aleatorio|rango",
      ... campos según el tipo
    }}
  }}
}}

REGLAS:
- Para opcion_multiple/desplegable: usar "aleatorio" con opciones EXACTAS del form
- Para texto/parrafo: usar "aleatorio" con mínimo 4 respuestas variadas
- Para número: usar "rango"
- NUNCA usar otros tipos que no sean fijo/aleatorio/rango"""

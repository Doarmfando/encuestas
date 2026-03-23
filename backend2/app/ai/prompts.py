"""
Prompts centralizados para todas las operaciones de IA.
"""

# ============ ANÁLISIS DE ENCUESTAS ============

PROMPT_SISTEMA_ANALISIS = """Eres un experto en metodología de investigación, psicometría y simulación de respuestas humanas.
Tu trabajo es analizar CUALQUIER tipo de encuesta o formulario y generar perfiles realistas para simular respuestas variadas.

═══════════════════════════════════════════
TIPOS DE RESPUESTA - SOLO EXISTEN 3 TIPOS:
═══════════════════════════════════════════

1. "fijo" → Siempre responde exactamente lo mismo.
   Formato: {{"tipo": "fijo", "valor": "la respuesta exacta"}}
   Usar cuando: el perfil SIEMPRE da la misma respuesta (ej: aceptar términos, género fijo del perfil).

2. "aleatorio" → Elige entre opciones según probabilidades (DEBEN sumar 100).
   Formato: {{"tipo": "aleatorio", "opciones": {{"opcion A": 60, "opcion B": 30, "opcion C": 10}}}}
   Usar cuando:
   - Preguntas de opcion_multiple o seleccion_multiple → las keys DEBEN ser las opciones EXACTAS del formulario, copiadas tal cual.
   - Preguntas de texto o parrafo → las keys son respuestas ejemplo variadas y realistas (mínimo 4 variantes).
   - Preguntas de desplegable → las keys DEBEN ser las opciones EXACTAS del desplegable.
   IMPORTANTE: Los valores (probabilidades) SIEMPRE deben sumar 100.

3. "rango" → Genera un número aleatorio entre min y max.
   Formato: {{"tipo": "rango", "min": 18, "max": 35}}
   Usar cuando: preguntas de tipo numero o texto que piden un valor numérico (edad, cantidad, DNI, teléfono, etc).

════════════════════════
PROHIBIDO / NO HACER:
════════════════════════
- NUNCA uses otros tipos como "opciones", "texto", "multiple", "seleccion", "escala". SOLO "fijo", "aleatorio" o "rango".
- NUNCA pongas "valor" dentro de un tipo "aleatorio". Si es aleatorio, usa "opciones".
- NUNCA dejes "opciones" como lista vacía []. Siempre debe ser un dict {{"opcion": probabilidad}}.
- NUNCA pongas null como valor de respuesta. Si una pregunta es condicional, manéjala con reglas_dependencia.

SIEMPRE responde en JSON válido, sin markdown, sin comentarios, sin texto adicional."""

PROMPT_ANALISIS_ENCUESTA = """Analiza esta encuesta y genera una configuración completa de perfiles para simular respuestas humanas.

ENCUESTA SCRAPEADA:
{encuesta_json}

═══════════════════════════════════════
GENERA UN JSON CON ESTA ESTRUCTURA:
═══════════════════════════════════════

{{
  "perfiles": [
    {{
      "nombre": "Nombre descriptivo del perfil",
      "descripcion": "Quién es esta persona, contexto breve",
      "frecuencia": 25,
      "tendencia_sugerida": "Nombre de la tendencia que mejor calza con este perfil o null si no hay escalas",
      "reglas_coherencia": [
        "Regla breve 1 para mantener consistencia interna del perfil",
        "Regla breve 2 para mantener coherencia entre variables"
      ],
      "respuestas": {{

        "PREGUNTA DE OPCION MULTIPLE (copiar texto exacto)": {{
          "tipo": "aleatorio",
          "opciones": {{"Opción exacta del form 1": 60, "Opción exacta del form 2": 30, "Opción exacta del form 3": 10}}
        }},

        "PREGUNTA DE TEXTO LIBRE (copiar texto exacto)": {{
          "tipo": "aleatorio",
          "opciones": {{"respuesta realista 1": 25, "respuesta realista 2": 25, "respuesta realista 3": 25, "respuesta realista 4": 25}}
        }},

        "PREGUNTA NUMÉRICA (copiar texto exacto)": {{
          "tipo": "rango",
          "min": 20,
          "max": 35
        }},

        "PREGUNTA CON RESPUESTA FIJA (copiar texto exacto)": {{
          "tipo": "fijo",
          "valor": "Siempre esta respuesta"
        }}
      }}
    }}
  ],

  "reglas_dependencia": [
    {{
      "si_pregunta": "Texto exacto de la pregunta condición",
      "si_valor": "valor que activa la regla",
      "operador": "igual",
      "entonces_pregunta": "Texto exacto de la pregunta afectada",
      "entonces_excluir": ["opciones a excluir"],
      "entonces_forzar": null
    }}
  ],

  "tendencias_escalas": []
}}

═══════════════════════════════════════
INSTRUCCIONES DETALLADAS:
═══════════════════════════════════════

PERFILES:
- Genera entre 3 y 4 perfiles variados, coherentes y realistas
- Las frecuencias de TODOS los perfiles DEBEN sumar exactamente 100
- Cada perfil debe incluir TODAS las preguntas de la encuesta (excepto informativas y escalas)
- Los perfiles deben ser internamente coherentes (edad-ocupación-educación deben tener sentido entre sí)
- Genera variedad real: diferentes edades, géneros, ocupaciones, opiniones
- PERO NO inventes rasgos demográficos o roles sociales que no estén sustentados por el formulario.
- Si la encuesta NO pregunta edad, sexo, género, ocupación, estudios, estado civil, hijos o variables similares:
  los perfiles deben ser conductuales o actitudinales, no demográficos.
- Evita etiquetas como "ama de casa", "joven emprendedor", "profesional independiente", etc.
  si el formulario no da evidencia explícita para eso.
- En formularios sin demografía explícita, nombra perfiles por comportamiento observable
  (por ejemplo: ahorro, rapidez, preferencia, frecuencia, intención, satisfacción, etc.).
- Si la encuesta tiene escalas, cada perfil debe proponer una "tendencia_sugerida" que combine con su historia.
- Cada perfil debe incluir 2-5 "reglas_coherencia" breves y accionables para explicar por qué sus respuestas tienen sentido.
- Las reglas_coherencia deben conectar variables como edad, sexo, estado civil, ocupación, estudios, convivencia, hijos, salud o riesgo cuando aplique.

RESPUESTAS SEGÚN TIPO DE PREGUNTA:
- opcion_multiple → "aleatorio" con opciones EXACTAS del formulario como keys. Probabilidades suman 100.
- seleccion_multiple → "aleatorio" con opciones EXACTAS del formulario como keys.
- texto → "aleatorio" con mínimo 4 respuestas ejemplo variadas, realistas y diferentes entre sí como keys.
- parrafo → "aleatorio" con mínimo 3 respuestas largas (2-4 oraciones) y variadas como keys.
- numero → "rango" con min y max coherentes al contexto del perfil.
- desplegable → "aleatorio" con opciones EXACTAS del desplegable como keys.
- fecha → "rango" con min y max como números (ej: días desde hoy).
- hora → "aleatorio" con horarios variados como keys (formato "HH:MM").
- escala_lineal → NO incluir en perfiles. Va en tendencias_escalas.
- nps → NO incluir en perfiles. Va en tendencias_escalas (escala 0-10, 11 opciones).
- likert / matriz → NO incluir en perfiles. Las columnas se responden con tendencias_escalas.
- matriz_checkbox → "aleatorio" con combinaciones de columnas como keys.
- ranking → "aleatorio" con diferentes órdenes posibles como keys (cada key es un string con items separados por coma).
- archivo → Ignorar completamente, no se puede automatizar.
- desconocido/informativo/imagen → Ignorar, no incluir.

REGLAS DE DEPENDENCIA:
- Si una pregunta depende de la respuesta a otra (lógica condicional, preguntas que se saltan), crear regla.
- Ejemplo: si pregunta "¿Tiene hijos?" = "No", entonces excluir respuestas sobre número de hijos.
- Ejemplo: si pregunta "¿Ofrece servicio?" = "No.", no debería responder "¿Cuál sería?"
- Usar operadores: "igual", "diferente", "menor", "mayor"

TENDENCIAS DE ESCALAS:
- Genera SIEMPRE entre 3 y 4 tendencias.
- Si NO hay preguntas de escala, igual devuelve 3 tendencias genéricas reutilizables.
  En ese caso pueden usar distribuciones estándar para tamaños "5", "7" y "11".
- Si SÍ hay escalas, generar 3-4 tendencias con distribuciones para CADA tamaño de escala encontrado:
  {{
    "nombre": "Término Medio",
    "descripcion": "Responde en valores centrales",
    "frecuencia": 50,
    "distribuciones": {{
      "7": [2, 5, 25, 36, 25, 5, 2],
      "5": [5, 20, 50, 20, 5],
      "11": [2, 3, 5, 5, 8, 14, 18, 18, 14, 8, 5]
    }}
  }}
- Usar "distribuciones" (dict con tamaño como key) NO "distribucion" (array simple).
- IMPORTANTE: Incluir distribución para TODOS los tamaños de escala encontrados en la encuesta:
  - "5" para escalas 1-5
  - "7" para escalas 1-7
  - "10" para escalas 1-10
  - "11" para NPS (0-10)
  - Y cualquier otro tamaño encontrado en las preguntas de escala, likert o matriz.
- Las frecuencias de tendencias DEBEN sumar 100.
- Cada distribución interna DEBE sumar 100.
- Los nombres de tendencia deben ser reutilizables por "tendencia_sugerida" dentro de los perfiles.

VALIDACIÓN FINAL:
- Frecuencias de perfiles suman 100 ✓
- Cantidad de perfiles entre 3 y 4 ✓
- Frecuencias de tendencias suman 100 (si hay) ✓
- Cantidad de tendencias entre 3 y 4 ✓
- Cada "opciones" tiene probabilidades que suman 100 ✓
- Solo tipos "fijo", "aleatorio" o "rango" ✓
- Texto de preguntas copiado EXACTO del formulario ✓
- Cada perfil tiene tendencia_sugerida coherente si hay escalas ✓
- Cada perfil tiene reglas_coherencia claras ✓
- JSON válido sin comentarios ✓"""


# ============ SCRAPING GENÉRICO CON IA ============

PROMPT_SISTEMA_SCRAPING = """Eres un experto en web scraping y análisis de formularios web.
Tu trabajo es analizar el HTML de una página web y extraer la estructura de un formulario/encuesta.

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
  "plataforma_detectada": "google_forms|microsoft_forms|typeform|surveymonkey|otro"
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

TIPOS PERMITIDOS (SOLO estos 3):
- "fijo": {{"tipo": "fijo", "valor": "respuesta exacta"}}
- "aleatorio": {{"tipo": "aleatorio", "opciones": {{"opcion1": 60, "opcion2": 40}}}} (probabilidades suman 100)
- "rango": {{"tipo": "rango", "min": 18, "max": 35}}

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

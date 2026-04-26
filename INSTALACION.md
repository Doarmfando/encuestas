# Sistema de Encuestas — Instalación y Uso

## Requisitos previos

| Herramienta | Versión mínima | Verificar con |
|---|---|---|
| Python | 3.10+ | `python --version` |
| Node.js | 18+ | `node --version` |
| PostgreSQL | 14+ | `psql --version` |
| npm | 9+ | `npm --version` |

---

## 1. Clonar / ubicar el proyecto

```
sistema-encuestas/
├── backend_sistema/
├── frontend/
└── INSTALACION.md
```

---

## 2. Base de datos (PostgreSQL)

Abre psql o pgAdmin y crea la base de datos:

```sql
CREATE DATABASE sistema_encuestas;
```

> Las tablas se crean automáticamente al iniciar el backend por primera vez (SQLAlchemy + Flask).

---

## 3. Backend (Flask + Python)

### 3.1 Entrar a la carpeta

```bash
cd backend_sistema
```

### 3.2 Crear entorno virtual

```bash
python -m venv venv
```

Activar:

- **Windows**
  ```bash
  venv\Scripts\activate
  ```
- **Linux / Mac**
  ```bash
  source venv/bin/activate
  ```

### 3.3 Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3.4 Instalar Playwright (navegador para el bot)

```bash
playwright install chromium
```

### 3.5 Configurar variables de entorno

Crea el archivo `.env` dentro de `backend_sistema/` con el siguiente contenido:

```env
# Base de datos
DATABASE_URL=postgresql://postgres:TU_PASSWORD@localhost:5432/sistema_encuestas

# OpenAI (requerido para análisis con IA)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o

# Anthropic (opcional)
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-4-20250514

# IA — parámetros generales
DEFAULT_AI_PROVIDER=openai
AI_TEMPERATURE=0.7
AI_MAX_TOKENS=4000

# Flask
SECRET_KEY=cambia-esto-por-una-clave-segura
```

> Reemplaza `TU_PASSWORD` con tu contraseña de PostgreSQL y `sk-...` con tu API key de OpenAI.

### 3.6 Iniciar el backend

**Opción A — Script rápido (Windows)**

Desde el explorador de archivos o una terminal, ejecutar:

```bash
backend_sistema\start.bat
```

Este script activa el entorno virtual automáticamente y lanza el servidor. No requiere pasos previos de activación manual.

**Opción B — Manual**

```bash
python server_new.py
```

El servidor queda corriendo en: **http://localhost:5105**

Endpoints disponibles:
- API: `http://localhost:5105/api/...`
- Documentación Swagger: `http://localhost:5105/docs`
- Health check: `http://localhost:5105/health`

---

## 4. Frontend (React + Vite)

### 4.1 Abrir otra terminal y entrar a la carpeta

```bash
cd frontend
```

### 4.2 Instalar dependencias

```bash
npm install
```

### 4.3 Iniciar el frontend en modo desarrollo

```bash
npm run dev
```

La aplicación queda disponible en: **http://localhost:1001**

> El frontend proxea automáticamente todas las llamadas a `/api` hacia `http://localhost:5105`. No se necesita configuración adicional.

---

## 5. Uso del sistema

### Flujo completo de un proyecto

```
1. Crear proyecto  →  2. Scrapear formulario  →  3. Analizar con IA  →  4. Ejecutar bot
```

**Paso 1 — Crear proyecto**
- Ir a "Mis Proyectos" → clic en **+ Nuevo Proyecto**
- Ingresar nombre, URL del formulario de Google Forms y descripción opcional
- Clic en **Crear**

**Paso 2 — Scrapear formulario**
- Dentro del proyecto, clic en **Scrapear**
- Opcional: activar "Modo invisible" (headless) o seleccionar plataforma manualmente
- El sistema detecta automáticamente todas las preguntas, opciones y páginas
- También se puede cargar la estructura manualmente con el editor JSON o visual

**Paso 3 — Analizar con IA / Configurar**
- Clic en **Analizar con IA** para que GPT genere perfiles y tendencias automáticamente
- Revisar el preview antes de guardar
- O usar **Generar plantilla sin IA** para una config base
- O **Importar** un archivo JSON de configuración desde `backend_sistema/examples/`

**Paso 4 — Ejecutar bot**
- Seleccionar cantidad de respuestas (1–500)
- Elegir velocidad:
  - **Balanced** — pausas naturales, simula comportamiento humano
  - **Turbo** — pausas mínimas *(requiere una ejecución Balanced 100% exitosa previa)*
  - **Turbo+** — sin pausas *(requiere una ejecución Balanced 100% exitosa previa)*
- Activar/desactivar **Headless** (invisible = sin ventana de navegador)
- Clic en **Ejecutar**
- Monitorear progreso y logs en tiempo real
- Al finalizar, descargar el Excel con los resultados

### Dashboard

- Clic en **Dashboard** en el encabezado para ver todas las ejecuciones activas en tiempo real
- Permite detener cualquier ejecución en curso

### Configuración de IA

- Clic en **Config** en el encabezado
- Agregar proveedor: seleccionar OpenAI o Anthropic, ingresar API key y modelo
- Clic en el proveedor para activarlo como predeterminado

---

## 6. Importar config desde archivo JSON

Los archivos de ejemplo están en `backend_sistema/examples/`.

1. Dentro de un proyecto scrapeado, ir a la sección **3. Configuración**
2. Clic en **Importar**
3. Seleccionar el archivo `.json` correspondiente
4. La config queda guardada y activa automáticamente

---

## 7. Levantar ambos servidores al mismo tiempo

Abre dos terminales:

**Terminal 1 — Backend**
```bash
# Opción rápida en Windows:
backend_sistema\start.bat

# O manualmente:
cd backend_sistema
venv\Scripts\activate
python server_new.py
```

**Terminal 2 — Frontend**
```bash
cd frontend
npm run dev
```

Luego abrir el navegador en **http://localhost:1001**

---

## 8. Errores comunes

| Error | Causa probable | Solución |
|---|---|---|
| `could not connect to server` | PostgreSQL no está corriendo | Iniciar el servicio PostgreSQL |
| `database "sistema_encuestas" does not exist` | BD no creada | Ejecutar `CREATE DATABASE sistema_encuestas;` en psql |
| `OPENAI_API_KEY not set` | Falta el `.env` o la key | Revisar el archivo `.env` en `backend_sistema/` |
| `playwright: executable doesn't exist` | Playwright no instalado | Ejecutar `playwright install chromium` |
| `Port 5105 already in use` | Otro proceso usa el puerto | Cerrar el proceso o cambiar el puerto en `server_new.py` |
| `Port 1001 already in use` | Otro proceso usa el puerto | Cambiar el puerto en `frontend/vite.config.ts` |

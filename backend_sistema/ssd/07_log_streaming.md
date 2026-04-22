# Log Streaming al Frontend

## Problema que resuelve

Cada ejecución corre en un hilo separado. El frontend hace polling a `/estado` y necesita
ver los logs en tiempo real. Python `logging` es global — se necesita separar los logs
por hilo para no mezclar ejecuciones concurrentes.

## Arquitectura

```
hilo de ejecución
  logger.info("msg")          ← cualquier módulo app.*
      ↓
  ThreadLocalLogHandler.emit()    (app/services/execution/log_capture.py)
      filtra: solo app.* loggers
      lee: thread_local.log_capture  ← LogCapture del hilo actual
      escribe en LogCapture.buffer
      ↓
  LogCapture.write()
      escribe en StringIO buffer
      también escribe en stdout original (visible en consola del servidor)

  ThreadLocalStdout.write()   ← wrapper de sys.stdout
      si hay log_capture activo → escribe en él
      sino → escribe en stdout original
```

## Setup en `app/__init__.py`

```python
from app.services.execution.log_capture import ThreadLocalLogHandler
import logging

thread_handler = ThreadLocalLogHandler()
thread_handler.setLevel(logging.DEBUG)
thread_handler.setFormatter(logging.Formatter("%(message)s"))
logging.getLogger().addHandler(thread_handler)  # root logger
```

El handler se registra en el root logger para capturar todos los subloggers `app.*`.

## Setup por hilo en `execution_service.py`

Al inicio de cada hilo:
```python
log_capture = LogCapture(original_stdout)
thread_local.log_capture = log_capture
sys.stdout = ThreadLocalStdout(original_stdout)
```

Al terminar el hilo: `thread_local.log_capture = None`

## Leer logs desde API

```python
execution_service.get_logs(execution_id)  # retorna str
# internamente: log_captures[execution_id].get_recent(max_chars=50000)
```

## Por qué SOLO app.*

`ThreadLocalLogHandler.emit()` tiene:
```python
if not record.name.startswith("app."):
    return
```

Sin este filtro, werkzeug (requests HTTP) y SQLAlchemy llenarían el buffer
con mensajes internos que el frontend no debería ver.

## Si los logs no llegan al frontend — checklist

1. ¿El logger del módulo usa `logging.getLogger(__name__)`?  
   El `__name__` debe empezar con `app.` para pasar el filtro.

2. ¿`ThreadLocalLogHandler` está en `logging.getLogger().handlers`?  
   Se registra en `app/__init__.py`. Si `create_app()` no corrió, no está.

3. ¿`thread_local.log_capture` está seteado en el hilo?  
   Solo existe durante `execution_service.execute()`.

4. ¿El módulo usa `print()` en vez de `logger`?  
   `print()` pasa por `ThreadLocalStdout` — también llega. Pero si `sys.stdout`
   fue reemplazado antes de crear el hilo, el hilo hereda el stdout correcto.

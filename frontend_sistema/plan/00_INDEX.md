# Plan: Migración Frontend → React + Vite

Estado: **PENDIENTE** — plan aprobado, sin implementar aún.

## Por qué migrar

El frontend actual (vanilla JS, ~3200 líneas) tiene dos problemas que escalan mal:

1. **Estado global mutable** — `currentProject`, `config`, `estructura`, etc. son variables sueltas
   modificadas por ~20 funciones. Cualquiera puede romper el estado de otra sin saberlo.

2. **Render por innerHTML** — el UI se construye con strings concatenados. Frágil, propenso a bugs
   visuales y difícil de extender sin tocar código no relacionado.

React resuelve ambos de raíz. Para un proyecto interno, el mayor beneficio es que
**agregar una nueva feature no requiere entender todo el resto del código** — cada componente
es independiente.

## Orden de lectura de este plan

| Archivo | Contenido |
|---|---|
| `01_stack.md` | Tecnologías elegidas con justificación |
| `02_arquitectura.md` | Estructura de carpetas y convenciones |
| `03_componentes.md` | Árbol de componentes y responsabilidades |
| `04_estado.md` | Gestión de estado: qué va dónde |
| `05_api.md` | Capa de API: hooks y queries |
| `06_pasos.md` | Plan de acción paso a paso |

## Criterios de diseño (uso interno)

- **Limpio sobre complejo** — si algo puede ser simple, debe serlo
- **Sin UI libraries pesadas** — los estilos actuales (CSS variables) se migran tal cual
- **TypeScript desde el inicio** — para que el IDE ayude, no para burocracia
- **Un solo archivo de tipos** — todos los tipos del dominio en `src/types.ts`
- **Cero dependencias innecesarias** — cada paquete que entra tiene que justificarse

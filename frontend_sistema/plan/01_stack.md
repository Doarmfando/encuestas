# Stack tecnológico

## Core

| Tecnología | Versión | Por qué |
|---|---|---|
| **React** | 18 | Componentes, estado local, ecosistema maduro |
| **Vite** | 5 | Build instantáneo, HMR real, sin config compleja |
| **TypeScript** | 5 | Tipos para los modelos del backend, autocompletado, errores en compile-time |

## Estado

| Paquete | Por qué |
|---|---|
| **Zustand** | Reemplaza las variables globales (`currentProject`, `config`, etc.). Sin boilerplate, sin Provider, ~30 líneas para todo el estado global |

No se usa Redux ni Context API — demasiado ceremony para un proyecto interno.

## API / Server state

| Paquete | Por qué |
|---|---|
| **TanStack Query** (React Query) | Reemplaza todos los `apiGet`/`apiPost` manuales + los `setInterval` de polling. Maneja cache, loading, error y refetch automático. El polling de `/estado` queda en 3 líneas |

## Estilos

| Decisión | Detalle |
|---|---|
| **CSS existente migrado** | Los archivos CSS actuales (`variables.css`, `components.css`, etc.) se copian sin cambios |
| **CSS Modules** | Cada componente tiene su `.module.css` para evitar colisiones de nombres |
| Sin Tailwind, sin styled-components | Innecesario para uso interno |

## Herramientas de desarrollo

| Tool | Para qué |
|---|---|
| **ESLint** + plugin React | Detecta errores comunes en hooks |
| **Prettier** | Formato consistente, sin discusiones |

## Lo que NO entra

- React Router — la app tiene solo 3 "vistas", con estado en Zustand es suficiente
- Redux / MobX — Zustand cubre todo el caso de uso
- UI libraries (MUI, Ant, Chakra) — ya hay estilos propios funcionales
- Jest / Testing Library — los tests del frontend no son prioridad para uso interno

## Comandos base

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install zustand @tanstack/react-query
npm run dev        # dev server en http://localhost:5173
npm run build      # build en dist/
```

El build de `dist/` puede ser servido directamente por Flask con `send_from_directory`
o como archivos estáticos independientes.

# 🧠 Segundo Cerebro v3

Sistema PKM (Personal Knowledge Management) personal, multi-usuario, que corre completamente en el navegador — sin servidor, sin base de datos, sin dependencias externas.

## ✨ Funcionalidades

### 🔐 Autenticación
- Registro y login con usuario + contraseña
- Contraseñas hasheadas con **SHA-256** (Web Crypto API) con salt por usuario
- Sesión con token UUID, expira en 8 horas automáticamente
- Datos completamente aislados por usuario via namespace en `localStorage`
- Múltiples usuarios en el mismo navegador sin interferencia

### 📝 Notas
- Crear, editar y eliminar notas
- Filtrado por área (Trabajo, Personal, Proyectos, Ideas)
- Búsqueda en tiempo real por título y contenido
- Tags personalizados

### ✅ Tareas
- Gestión completa de tareas con prioridades (Alta / Media / Baja)
- Filtros por estado (pendientes / completadas) y por área
- Fecha límite y vinculación a proyectos
- Check para completar directamente desde el dashboard

### ◈ Proyectos
- Proyectos con descripción, área y emoji
- Barra de progreso automática basada en tareas vinculadas

### ₡ Finanzas
- Registro de ingresos y gastos por categoría
- Presupuesto mensual configurable por categoría con barras de progreso
- Resumen mensual (ingresos / gastos / balance)
- Alertas visuales al superar el presupuesto

### ◎ Ahorros & Deudas
- Metas de ahorro con progreso y fecha objetivo
- Seguimiento de deudas con tasa de interés y fecha de vencimiento
- Botón de abono/pago para actualizar progreso

### ◉ Hábitos
- Hábitos diarios, laborables o de fin de semana
- Check diario con mini-calendario de los últimos 7 días
- Racha (streak) de días consecutivos
- Vista rápida en el dashboard

### ▣ Inventario del Hogar
- Artículos por categoría (electrodomésticos, electrónica, muebles, etc.)
- Valor estimado, cantidad, ubicación y estado
- Valor total del inventario calculado automáticamente
- Filtros por categoría y búsqueda

### 🤖 Buscar con IA
- Integración con la API de Claude (Anthropic)
- El asistente tiene contexto de **todos** tus datos: notas, tareas, finanzas, hábitos e inventario
- Responde preguntas sobre tu información personal

---

## 🚀 Cómo usar

### Opción 1 — Abrir directo
```
Abre index.html en tu navegador. No necesita servidor.
```

### Opción 2 — GitHub Pages
1. Subí el repositorio a GitHub
2. Ve a **Settings → Pages**
3. Seleccioná la rama `main` y la carpeta `/root`
4. Tu app estará disponible en `https://tu-usuario.github.io/segundo-cerebro`

> ⚠️ **Nota sobre GitHub Pages:** Los datos se guardan en `localStorage` del navegador. Cada dispositivo/navegador tiene su propio almacenamiento. No hay sincronización entre dispositivos.

---

## 🔑 Configurar la API de Claude (opcional)

El módulo de IA requiere acceso a la API de Anthropic. Para habilitarlo:

1. Obtené tu API key en [console.anthropic.com](https://console.anthropic.com)
2. La app funciona normalmente sin la API — solo el módulo "Buscar con IA" la requiere

> **Importante:** Esta app llama a la API directamente desde el navegador. Para producción real, se recomienda usar un backend proxy para no exponer la API key.

---

## 🛡️ Seguridad y privacidad

| Aspecto | Detalle |
|---|---|
| Almacenamiento | `localStorage` del navegador (local, no se envía a ningún servidor) |
| Contraseñas | Hash SHA-256 con salt por usuario — nunca texto plano |
| Sesión | `sessionStorage` — se destruye al cerrar el navegador |
| Aislamiento | Namespace `scb3_data_{usuario}_{módulo}` por usuario |
| Dependencias externas | Solo Google Fonts (tipografía) y Anthropic API (IA opcional) |

---

## 📁 Estructura del proyecto

```
segundo-cerebro/
├── index.html        ← App completa (single-file)
├── README.md         ← Este archivo
├── LICENSE           ← MIT License
└── .gitignore        ← Archivos ignorados
```

---

## 🛠️ Stack técnico

- **HTML5 + CSS3 + JavaScript vanilla** — sin frameworks
- **Web Crypto API** — hashing SHA-256 nativo del navegador
- **localStorage / sessionStorage** — persistencia y sesión
- **Anthropic Claude API** — módulo de IA
- **Google Fonts** — Syne, Newsreader, JetBrains Mono

---

## 📝 Licencia

MIT — libre para usar, modificar y distribuir.

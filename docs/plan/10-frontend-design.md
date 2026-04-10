# 10 — Diseño de Frontend y UX

## 1. Stack del frontend

| Tecnología | Versión | Rol |
|-----------|---------|-----|
| Next.js | 15 | Framework React con SSR, App Router |
| TypeScript | 5.x | Tipado estricto |
| Tailwind CSS | 4.x | Utility-first CSS |
| shadcn/ui | latest | Componentes accesibles y customizables |
| Zustand | 5.x | Estado global ligero |
| Socket.io-client | 4.x | WebSocket para chat |
| React Query | 5.x | Server state, cache, mutations |
| Framer Motion | 11.x | Animaciones |
| Lucide React | latest | Iconos |

## 2. Estructura de páginas

```
app/
├── (auth)/
│   ├── login/page.tsx
│   ├── register/page.tsx
│   └── layout.tsx
│
├── (app)/
│   ├── layout.tsx              ← Layout principal con sidebar
│   ├── page.tsx                ← Dashboard / Nuevo caso
│   │
│   ├── cases/
│   │   ├── page.tsx            ← Lista de casos
│   │   └── [caseId]/
│   │       ├── page.tsx        ← Chat del caso
│   │       └── summary/
│   │           └── page.tsx    ← Resumen clínico
│   │
│   └── settings/
│       └── page.tsx            ← Configuración del usuario
│
└── layout.tsx                  ← Root layout
```

## 3. Pantallas principales

### 3.1 Chat del caso (pantalla principal)

```
┌─────────────────────────────────────────────────────┐
│  ← MedAgent    Caso: Dolor abdominal    [⚙️] [📋]  │
├──────────┬──────────────────────────────────────────┤
│          │                                          │
│ SIDEBAR  │              CHAT AREA                   │
│          │                                          │
│ Casos    │  ┌────────────────────────────────────┐  │
│          │  │ 🤖 Sistema                         │  │
│ • Dolor  │  │ Bienvenido/a a MedAgent...         │  │
│   abdom. │  └────────────────────────────────────┘  │
│          │                                          │
│ • Fatiga │  ┌────────────────────────────────────┐  │
│   crón.  │  │ 👤 Tú                              │  │
│          │  │ Tengo dolor en la parte baja del    │  │
│ • Dolor  │  │ abdomen desde hace 3 días...        │  │
│   cabeza │  └────────────────────────────────────┘  │
│          │                                          │
│ + Nuevo  │  ┌────────────────────────────────────┐  │
│   caso   │  │ 🤖 MedAgent                        │  │
│          │  │                                    │  │
│          │  │ Analizando tu consulta...           │  │
│          │  │ ████████░░░░ Evaluando áreas...     │  │
│          │  │                                    │  │
│          │  │ [Agentes activos: Triage, Med.Gen]  │  │
│          │  └────────────────────────────────────┘  │
│          │                                          │
│          │  ┌────────────────────────────────────┐  │
│          │  │ 🤖 MedAgent                        │  │
│          │  │                                    │  │
│ CONTEXTO │  │ ## Análisis de tu consulta          │  │
│ DEL CASO │  │                                    │  │
│          │  │ Entiendo tu preocupación por el     │  │
│ Triage:  │  │ dolor abdominal...                  │  │
│ 🟡 Medio │  │                                    │  │
│          │  │ ## Áreas que evaluamos              │  │
│ Espec:   │  │ - Medicina General                  │  │
│ Gastro   │  │ - Gastroenterología                 │  │
│ Med.Int. │  │                                    │  │
│          │  │ ## Próximos pasos sugeridos          │  │
│ Docs: 1  │  │ 1. ...                              │  │
│          │  │                                    │  │
│ Alarmas: │  │ ⚠️ Esta orientación no constituye   │  │
│ Ninguna  │  │ un diagnóstico médico.              │  │
│          │  │                                    │  │
│          │  │ [Gastro] [Med.General] [Med.Interna] │ │
│          │  └────────────────────────────────────┘  │
│          │                                          │
│          ├──────────────────────────────────────────┤
│          │ [📎] Escribe tu mensaje...        [➤]   │
│          │                                          │
└──────────┴──────────────────────────────────────────┘
```

### 3.2 Componentes clave del chat

#### Indicador de progreso de agentes
```
┌──────────────────────────────────────┐
│  Analizando tu consulta...           │
│                                      │
│  ✅ Triage completado               │
│  ✅ Clasificación completada        │
│  🔄 Consultando especialidades...   │
│     • Medicina General              │
│     • Gastroenterología             │
│  ⏳ Revisión pendiente              │
│  ⏳ Síntesis pendiente              │
│                                      │
│  Tiempo estimado: ~10 segundos       │
└──────────────────────────────────────┘
```

#### Tags de especialidades en la respuesta
```
Especialidades que analizaron tu caso:
[🏥 Med. General] [🔬 Gastroenterología] [⚕️ Med. Interna]
```

#### Preguntas de seguimiento del sistema
```
┌──────────────────────────────────────┐
│  Para completar el análisis,         │
│  necesito preguntarte:               │
│                                      │
│  1. ¿El dolor es constante o va     │
│     y viene?                         │
│     [Constante] [Intermitente]       │
│                                      │
│  2. Del 1 al 10, ¿qué tan          │
│     intenso es?                      │
│     [1-3 Leve] [4-6 Moderado]       │
│     [7-10 Severo]                    │
│                                      │
│  3. ¿Tienes fiebre?                 │
│     [Sí] [No] [No estoy seguro/a]  │
│                                      │
└──────────────────────────────────────┘
```

#### Alerta de escalamiento
```
┌──────────────────────────────────────┐
│  🔴 ATENCIÓN IMPORTANTE              │
│                                      │
│  Los síntomas que describes          │
│  podrían indicar una situación       │
│  que requiere evaluación médica      │
│  URGENTE.                            │
│                                      │
│  ☎️ Emergencias: 107 / 911          │
│                                      │
│  [Entendido, buscaré atención]       │
│  [Quiero más información]            │
└──────────────────────────────────────┘
```

### 3.3 Upload de documentos

```
┌──────────────────────────────────────┐
│           📄 Subir documento         │
│                                      │
│  ┌──────────────────────────────┐   │
│  │                              │   │
│  │   Arrastra tu archivo aquí   │   │
│  │        o                     │   │
│  │   [Seleccionar archivo]      │   │
│  │                              │   │
│  │   PDF, JPG, PNG, DOCX       │   │
│  │   Máximo 20 MB               │   │
│  │                              │   │
│  └──────────────────────────────┘   │
│                                      │
│  Tipos aceptados:                    │
│  • Resultados de laboratorio         │
│  • Recetas médicas                   │
│  • Informes clínicos                 │
│  • Fotos de documentos               │
│                                      │
└──────────────────────────────────────┘
```

### 3.4 Resumen clínico del caso

```
┌──────────────────────────────────────────┐
│  📋 Resumen clínico                      │
│  Caso: Dolor abdominal recurrente        │
│  Última actualización: Hace 2 horas      │
├──────────────────────────────────────────┤
│                                          │
│  Motivo de consulta                      │
│  Dolor en la parte baja del abdomen      │
│  desde hace 3 días, intermitente,        │
│  intensidad 5/10.                        │
│                                          │
│  Problemas activos                       │
│  • Dolor abdominal bajo a estudio        │
│                                          │
│  Medicación actual                       │
│  • Metformina 850mg                      │
│                                          │
│  Alergias                                │
│  • Penicilina                            │
│                                          │
│  Hipótesis activas                       │
│  • Síndrome de intestino irritable       │
│  • Gastroenteritis                       │
│                                          │
│  Estudios sugeridos pendientes           │
│  • Hemograma completo                    │
│  • PCR                                   │
│  • Ecografía abdominal                   │
│                                          │
│  ⚠️ Signos de alarma a vigilar          │
│  • Fiebre >38.5°C                        │
│  • Sangrado rectal                       │
│  • Dolor que no cede con analgésicos     │
│                                          │
│  Nivel de atención: 🟡 Consultar en     │
│  24-48 horas si persiste                 │
│                                          │
│  Timeline                                │
│  ─── 05 Abr 10:00 ─ Caso creado        │
│  ─── 05 Abr 10:01 ─ Triage: Amarillo   │
│  ─── 05 Abr 10:02 ─ Gastro activada    │
│  ─── 05 Abr 10:05 ─ Lab subido         │
│  ─── 05 Abr 11:30 ─ Resumen actualizado│
│                                          │
└──────────────────────────────────────────┘
```

## 4. Temas y diseño visual

### Paleta de colores

```css
/* Colores principales — Profesional médico pero cálido */
--primary: #2563EB;        /* Azul médico — confianza */
--primary-light: #3B82F6;
--primary-dark: #1D4ED8;

--secondary: #10B981;      /* Verde — salud, bienestar */
--secondary-light: #34D399;

/* Niveles de triage */
--triage-green: #22C55E;   /* Sin urgencia */
--triage-yellow: #EAB308;  /* Atención moderada */
--triage-red: #EF4444;     /* Urgencia */

/* Backgrounds */
--bg-primary: #FFFFFF;
--bg-secondary: #F8FAFC;
--bg-chat: #F1F5F9;

/* Texto */
--text-primary: #0F172A;
--text-secondary: #475569;
--text-muted: #94A3B8;

/* Dark mode */
--dark-bg: #0F172A;
--dark-surface: #1E293B;
--dark-text: #E2E8F0;
```

### Tipografía
- **Headings**: Inter (weight 600-700)
- **Body**: Inter (weight 400)
- **Monospace**: JetBrains Mono (para datos clínicos/lab)

## 5. Responsive design

| Breakpoint | Layout |
|-----------|--------|
| Desktop (>1024px) | Sidebar + Chat + Panel lateral |
| Tablet (768-1024px) | Sidebar colapsable + Chat |
| Mobile (<768px) | Solo Chat, sidebar en drawer |

## 6. Accesibilidad

- Todos los componentes shadcn/ui son accesibles por defecto (ARIA)
- Contraste mínimo WCAG AA
- Navegación por teclado completa
- Screen reader compatible
- Textos alternativos en imágenes
- Focus visible en todos los elementos interactivos

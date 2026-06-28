# ADR-001 — Refactor estructural de DITO hacia un dashboard operacional

| Campo | Valor |
|---|---|
| **Estado** | Propuesto · v2 (unificado) |
| **Fecha** | 2026-06-06 (rev. 2026-06-07) |
| **Decisores** | Equipo Dito Estudio (Omar, Carlos, Irving) |
| **Contexto técnico** | Flask + SQLAlchemy + SQLite (WAL) + Jinja2 + Bootstrap 5.3 + APScheduler + Anthropic API |
| **Documentos hermanos** | `DITO-schema-base.md` (modelo de datos + layout), mockups HTML |

> **v2** unifica en un solo proceso las decisiones de arquitectura de datos
> (v1) con las decisiones de producto/UI confirmadas en los mockups: navegación
> de 4 áreas, fichas temporales, selector de fecha con presets, paneles por
> tipo de cliente, panel de campañas y diseño responsive.

---

## 1. Resumen de la decisión

Se **refactoriza** la estructura existente de DITO (no se reescribe desde cero)
para convertirlo de un dashboard orientado al desarrollador en una **herramienta
operacional para mercadólogos**, cuya pantalla principal responde "¿qué cuentas
tuvieron algo inusual ayer?" en menos de 5 segundos.

El refactor conserva intactos los motores que funcionan (sync, clientes de API,
subsistema de IA, reportes) y reorganiza presentación y modelo de datos alrededor
de cuatro conceptos: **objetivos por cuenta**, **budget pacing**, **alertas
persistentes** y **referencia histórica congelada**. La aplicación se estructura
en **cuatro áreas de navegación**: Centro de control, Desglose mensual,
Herramientas y Datos del cliente.

---

## 2. Contexto y problema

### 2.1 Qué es DITO hoy
Dashboard interno + alertas + reporting para una agencia que opera Google Ads y
Meta Ads para 10-20 clientes. Sincroniza métricas diarias a SQLite, tiene un
subsistema de IA (`CLAUDE/`) con detección de anomalías (Haiku) y reportes
(Sonnet), y genera digests por email.

### 2.2 El problema descubierto
DITO tiene los datos correctos pero está construido desde la perspectiva del
desarrollador, no del mercadólogo. El flujo real del mercadólogo hoy: abrir
Google Ads y Meta Ads manualmente cuenta por cuenta, y llenar un Excel de KPIs
a mano cada semana. Las tres preguntas que el sistema debe responder sin que el
usuario busque:
- **Matutina:** ¿qué cuentas tuvieron algo inusual ayer?
- **De control:** ¿cómo voy contra el presupuesto/objetivo de cada cliente?
- **De mayor costo de tiempo:** ¿cuál es el CPL/CPA/ROAS real y actualizado?

### 2.3 Estado real del sistema (factores de decisión)
1. **Nadie depende del sistema todavía** — prototipo/MVP en uso, no crítico.
2. **El código es manejable** — se le agregan cosas sin fricción.
3. **El destino deseado es el mismo stack** (Flask/SQLite) con estructura limpia.

### 2.4 La pregunta que este ADR resuelve
> ¿Refactorizar la estructura existente, o reescribir desde cero?

---

## 3. Opciones consideradas

### Opción A — Refactor estructural agresivo *(elegida)*
Conservar los motores que funcionan, reorganizar estructura y modelo de datos.
Introducir lo nuevo vía migraciones idempotentes sobre la base ya poblada.
- **Pros:** conserva ~70% de código probado; cero pérdida de datos; API + IA
  (lo más difícil de reconstruir) quedan intactos; valor incremental.
- **Contras:** arrastra decisiones previas; exige disciplina anti-legacy; el
  modelo crece por ALTER.

### Opción B — Rebuild desde cero (mismo stack)
- **Pros:** modelo limpio de una vez.
- **Contras:** reconstruir clientes de API + z-score + OAuth/CSRF/scheduler (todo
  funciona); alto riesgo de re-introducir bugs; semanas sin entregar valor.

### Opción C — Rebuild con cambio de stack (FastAPI/Postgres/SPA)
- **Contras:** todos los de B multiplicados; el volumen no justifica Postgres;
  complejidad operacional sin un problema que la exija.

---

## 4. Decisión y justificación

**Se elige la Opción A (refactor estructural agresivo).**

> Un rebuild se justifica cuando el código **te frena** o cuando vas a **cambiar
> de stack**. En DITO no aplica ninguna: el código es manejable y el stack se
> conserva. Reescribir desde cero sería tirar ~70% de código que funciona —
> incluyendo lo más difícil (API + IA) — para ganar solo un modelo de datos
> limpio que de todos modos se logra con migraciones.

Que **nadie dependa del sistema aún** hace el refactor de bajo riesgo, no inclina
hacia rebuild. La única ventaja del rebuild (modelo limpio de una vez) se
neutraliza con las migraciones idempotentes que el proyecto ya usa.

---

## 5. Arquitectura de la aplicación (decisión de producto)

### 5.1 Cuatro áreas de navegación
La app se organiza en cuatro destinos en el sidebar, separando la **operación**
de la **administración**:

| Área | Propósito | Naturaleza |
|---|---|---|
| **Centro de control** | "¿Qué cuentas necesitan atención?" — briefing diario | Operacional |
| **Desglose mensual** | "¿Es rentable esta cuenta?" — ROAS + ROI con honorarios | Analítica |
| **Herramientas** | Acciones sobre cuentas | Acción |
| **Datos del cliente** | Info administrativa (honorarios, contrato, specs) | Administración |

**Decisión clave:** *Datos del cliente* es un módulo **independiente** de la
operación diaria. No vive en el flujo de monitoreo. Pero se conecta con el
*Desglose mensual* a través de los **honorarios**, que alimentan el cálculo de ROI.

### 5.2 Centro de control — solo señal, sin datos agregados
**Decisión:** el centro de control NO muestra métricas agregadas (totales de
gasto, etc.). En su lugar abre con **tres fichas temporales** que son atajos de
rango y muestran solo señal operativa (cuántas cuentas necesitan atención):
- "¿Qué pasó ayer?"
- "¿Qué pasó la semana pasada?"
- "¿Cómo va este mes?"

Debajo: la zona "¿qué pasó ayer?" (anomalías que surgen solo cuando existen) y la
tabla multi-cuenta peor-primero. Razón: el centro de control es operacional
(¿qué atender?), no analítico (¿cuánto se gastó?). Los agregados viven en el
Desglose mensual, donde sí aportan.

### 5.3 Selector de fecha con presets estilo Google Ads
**Decisión:** el selector (arriba a la derecha) tiene presets en español: Hoy,
Ayer, Esta semana, Últimos 7 días, Semana pasada, Últimos 14/15 días, Este mes,
Últimos 30 días, Mes pasado, Todo el tiempo, Personalizado (con calendario) +
toggle Comparar. Las fichas temporales (§5.2) son atajos a estos rangos.

### 5.4 Dashboards separados por plataforma
Google y Facebook se analizan y comparan de forma **independiente** (`/google`,
`/facebook`), nunca combinados ni sumados (monedas y definiciones distintas). El
mismo servicio `briefing.py` sirve a ambos con un parámetro de plataforma.

### 5.5 Detalle de cuenta — paneles por tipo de cliente
**Decisión:** el detalle de cada cuenta se adapta a su `client_type` con una
estructura común pero métricas y visualizaciones propias:

| | Métrica héroe | Visualización propia |
|---|---|---|
| **ecommerce** | ROAS (vs normal + objetivo) | embudo de conversión (impr → clic → carrito → checkout → compra) |
| **leads** | CPL (vs normal + objetivo) | calidad del lead (convertidos) + origen (formularios vs llamadas) |
| **mensajes** | Costo por mensaje | banda de frecuencia (verde <2.5 / ámbar 2.5–3.5 / rojo >3.5) |

Todos comparten: métricas secundarias, análisis IA inline, tendencia de 7 días, y
un **panel de campañas** al fondo (§5.6).

### 5.6 Panel de campañas en el detalle
**Decisión:** cada detalle de cuenta cierra con un panel de campañas en su propio
recuadro: nombre, **estado (activa/pausada)** y métricas principales adaptadas al
tipo (ecommerce: ROAS/ventas/CPA; leads: leads/CPL/CTR; mensajes:
mensajes/costo-msj/frecuencia). Usa los modelos `Campaign` + `CampaignMetric`
existentes y `Campaign.status` — **no requiere schema nuevo**.

### 5.7 Diseño responsive / móvil — requisito de primera clase
**Decisión:** el diseño es responsive desde el inicio, no una adaptación
posterior. Sidebar → hamburguesa, tabla multi-cuenta → tarjetas, selector de
fecha → bottom sheet, paneles → columna única. Mobile no es un afterthought.

### 5.8 Identidad visual — brand guide de Dito (estricto)
Paleta azul `#3333FF` (acción) / menta `#22E0BE` (positivo, gráficas) / amarillo
`#FFE100` (highlight único por composición) / negro (caballo de batalla); papel
`#FAFAF7` superficie; grotesca en minúsculas para títulos; mono (JetBrains) para
cifras; triángulo de play como única marca propia; **sin degradados, sin emoji**.
Sub-paleta funcional para estado (rojo crítico, ámbar atención, menta ok),
siempre con etiqueta de texto (accesibilidad/daltonismo).

---

## 6. Qué se conserva, reorganiza y crea

### 6.1 Se conserva INTACTO
`google_ads_client.py`, `facebook_ads_client.py`, `sync.py`/`sync_config.py`,
`CLAUDE/anomalies.py`+`alerts.py`+`zscore.py`+`daily_digest.py`+`reports.py`+
`emailer.py`, `auth.py`, `csrf.py`, `ad_copy_review.py` + servicios `ad_*`, y el
mecanismo de migraciones de `database.py`.

### 6.2 Se reorganiza
- `routes/dashboard.py` → dos dashboards (`/google`, `/facebook`) con fichas
  temporales + zona de anomalías + tabla peor-primero.
- `routes/accounts.py` → paneles por `client_type` + panel de campañas.
- `routes/history.py` → desglose por tipo + origen de campo + cierre de mes.
- `routes/clients.py` → módulo Datos del cliente independiente.
- `services/metrics.py` → agregaciones multi-cuenta con deltas, por plataforma.
- `services/notifications.py` → persiste en tabla `Alert`.
- `models.py` → campos de target en `Account`, `Alert`, `AccountBaseline`,
  `MonthlyHistory` reestructurada, `CLIENT_TYPE_MESSAGES`.

### 6.3 Se crea nuevo
- `services/briefing.py` — orquestador del briefing (recibe `platform` + `range`).
- `services/pacing.py` — aritmética de budget pacing.
- `services/alert_store.py` — persistencia de `Alert` + estados.
- `services/baseline.py` — recalcula `AccountBaseline` al cerrar mes.
- `services/conversion_labels.py` — normalización Google/Meta → español.
- Templates: `dashboard/briefing.html`, `accounts/panel_{ecommerce,leads,mensajes}.html`,
  `history/` por tipo, y la vista de Datos del cliente.

---

## 7. Modelo de datos — decisiones

### 7.1 Objetivos por cuenta (bloquea todo lo demás)
En `Account`: `target_cpa`, `target_roas`, `monthly_budget`,
`primary_conversion_label`, `target_source` ('derived'|'manual'). El `target_cpa`
provisional se **deriva** del promedio de 60 días (baseline automático) para no
bloquear el sistema esperando captura manual; `monthly_budget` sí es captura
manual (dato de negocio).

### 7.2 Tabla `Alert` (persistencia de "¿qué pasó ayer?")
Persiste anomalías con `status` (new/acknowledged/resolved) y dedup por
`(account_id, date, kind)`. El `anomaly_cache.json` queda como cache de
explicaciones Haiku; `Alert` es la fuente de verdad del historial.

### 7.3 Reconciliación de campos duplicados (decisión crítica)
El generador de reportes proponía campos en `Client` que ya existen. Se decide:
- `report_contact_email` → usar `Client.contact_email` existente.
- `ticket_value` → leads = `Client.average_lead_value`; ecommerce = valor real de
  `CampaignMetric`.
- `conversion_label` → `Account.primary_conversion_label`.
- `suggested_budget` → derivado de `monthly_budget × 1.5`.

**Principio:** estos campos se diseñan UNA vez para los dos features (dashboard y
reportes), no dos veces. Se hace en la Fase 0, antes de tocar nada más.

### 7.4 `MonthlyHistory` reestructurada — motor de rentabilidad
Una tabla con campos por tipo + origen por campo (`manual_fields`,
`investment_source`), `client_type_snapshot`, `is_closed`, y derivadas de
rentabilidad congeladas (`generated_value`, `total_cost`, `roi`). El ROI
**incluye honorarios**. `mensajes` deja ROI nulo (solo volumen + costo/mensaje).
Detalle completo en `DITO-schema-base.md`.

### 7.5 `AccountBaseline` — referencia histórica congelada
Promedios sobre toda la historia de meses cerrados, recalculados solo al marcar
`is_closed=True`. Alimenta el patrón "actual vs tu normal" en toda la UI.

### 7.6 El panel de campañas no agrega schema
Usa `Campaign` + `CampaignMetric` + `Campaign.status` existentes.

### 7.7 Índice
`CREATE INDEX IF NOT EXISTS ix_cm_date_campaign_id ON campaign_metrics (date, campaign_id);`

---

## 8. Principios de arquitectura que el refactor debe respetar
1. **Route → Service → Client.** El briefing es servicio, no lógica en ruta.
2. **Constantes de plataforma, nunca literales.**
3. **Migraciones idempotentes**, nunca `create_all()` sobre columnas existentes.
4. **Un número nunca sin contexto** (valor + delta + vs normal/target).
5. **CSRF en toda ruta POST que mute estado.**
6. **IA explicable y silenciosa por defecto** (inline + "por qué", sin saturar).
7. **El sync y los clientes de API no se tocan.**
8. **Plataformas nunca se suman** (monedas/definiciones distintas).
9. **Responsive de primera clase**, no adaptación posterior.

---

## 9. Plan de ejecución por fases (unificado)

Incremental, una fase por rama/commit; el sistema funciona al final de cada una.

### Fase 0 — Reconciliación + migraciones *(bloquea todo)*
Campos finales (§7.3); ALTER idempotente de `Account` + `MonthlyHistory`; tablas
`Alert` + `AccountBaseline`; índice; `CLIENT_TYPE_MESSAGES` con retro-compat;
derivar `target_cpa` provisional. **Done:** schema migrado sin pérdida de datos.

### Fase 1 — Persistencia de alertas
`alert_store.py` + `notifications.py` escriben en `Alert`. **Done:** anomalías
con estado e historial.

### Fase 2 — Briefing + pacing + baseline
`pacing.py`, `briefing.py` (platform + range), `baseline.py`. **Done:** dataset
completo del briefing + referencia congelada.

### Fase 3 — Centro de control (la landing nueva)
`/google` y `/facebook` con fichas temporales, selector de fecha con presets,
zona de anomalías, tabla peor-primero. Responsive. **Done:** el mercadólogo ve
qué cuentas necesitan atención en <5s.

### Fase 4 — Detalle por tipo + campañas + normalización
Paneles `ecommerce`/`leads`/`mensajes` con métrica héroe, visualización propia y
panel de campañas. Diccionario de normalización de conversiones. **Done:** nombres
legibles, métricas por tipo, campañas con estado.

### Fase 5 — Desglose mensual (rentabilidad)
Formulario por tipo con origen de campo + captura manual + cierre de mes; ROI con
honorarios; resumen analítico. **Done:** rentabilidad por cuenta-mes.

### Fase 6 — Herramientas + Datos del cliente
Herramientas (Generar reporte, Revisión de anuncios, Carga manual de
conversiones). Módulo Datos del cliente independiente, conectado por honorarios.
**Done:** las cuatro áreas operativas.

### Fase 7 — Reportes (reusa el modelo reconciliado)
El generador consume `primary_conversion_label` + targets existentes. **Done:**
reporte desde el modelo unificado.

---

## 10. Consecuencias

### Positivas
- Valor incremental; el sistema funciona al final de cada fase.
- Cero pérdida de datos.
- API + IA intactos.
- Modelo de datos unificado: dashboard, desglose y reportes comparten campos.
- Operación y administración separadas pero conectadas por honorarios.

### Negativas / riesgos
- El refactor arrastra decisiones previas (mitiga: criterio de done por fase).
- El modelo crece por ALTER (mitiga: Fase 0 reconcilia antes de todo).
- `target_cpa` derivado es aproximado (mitiga: flag derivado/confirmado).

### Neutrales
- Stack sin cambios; SQLite sigue siendo suficiente.

---

## 11. Revisión
Se revisa si cambia alguno de los tres hechos de §2.3 (el sistema se vuelve
crítico, el código se vuelve doloroso, o surge razón para cambiar de stack).

---

*Fin del ADR-001 v2.*

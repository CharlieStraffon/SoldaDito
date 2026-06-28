# Prompt para Claude Code — Build de DITO / SoldaDito desde cero

Vas a construir **DITO (SoldaDito)** desde cero: la capa analítica y de resultados financieros sobre las cuentas publicitarias de Meta y Google de una agencia de marketing. Es un **build limpio (greenfield)** — no parches de código existente. El código anterior y los screenshots son solo referencia; partimos de un repo formateado y consistente para evitar errores heredados.

**North star del sistema:** responder en menos de 5 segundos *"¿qué cuentas tuvieron algo inusual?"* y *"¿es rentable esta cuenta para el cliente?"*.

---

## 0. Antes de escribir una sola línea

Lee, en este orden, los documentos en `/docs` — son la fuente de verdad:
1. `CLAUDE.md` (raíz) — reglas duras y orientación
2. `ADR-001-refactor-dito.md` — arquitectura, navegación de 4 áreas, principios
3. `ADR-002` piezas 1–3 — modelo de datos, motor financiero, alertas y proceso
4. `contrato-motor-financiero-kpis-prioritarios.md` — **las fórmulas**
5. `matriz-categorizacion-implicaciones-modelo.md` — el tipo de cada cuenta
6. `especificacion-seed-dito.md` — qué se carga y cómo

**Si una decisión no está en esos documentos, pregunta antes de inventar.** No re-litigues decisiones ya tomadas.

---

## 1. Stack (fijo)

Flask · SQLAlchemy · SQLite (WAL) en `instance/dito.db` · Jinja2 · Bootstrap 5.3 · APScheduler · Flatpickr · API Anthropic (Haiku para triage de anomalías, Sonnet para reportes). Estructura:

```
webapp/        models.py · blueprints (routes) · services · clients (API) · templates · static
migrations/    Alembic / Flask-Migrate
scripts/seed.py
tests/
docs/
instance/dito.db   (no se versiona)
.env / .env.example
```

Patrón obligatorio: **Route → Service → Client**. Una ruta nunca llama a la API externa directo.

---

## 2. No negociables (resumen — detalle en CLAUDE.md)

1. **Plataformas nunca se suman.** Google y Facebook separados, cada uno su moneda (MXN/USD/COP). El ROI-con-honorarios se calcula a nivel **engagement = cliente × plataforma**.
2. **`panel_type` explícito**, sembrado de la matriz. **Nunca derivarlo del evento de conversión** (ese fue el bug original). Cuenta sin mapeo → `pendiente_de_clasificar`, jamás un tipo asumido.
3. **Valor de leads solo del cierre manual.** Si `value_source = manual_close`, el valor de plataforma se ignora en todo cálculo.
4. **ROI canónico, una sola definición** (ver §3).
5. **Margen editable**, default `0.35`, en `Client.margin_pct`. **Nunca hardcodear.**
6. **Origen por campo:** API / manual / calculado / config, rastreado con `*_source`. Campos API son read-only.
7. **Sin Notion en vivo** — todo nativo y sembrado.
8. **Constantes de plataforma, nunca literales.** CSRF en todo POST que mute estado. Un número nunca sin contexto (valor + delta + vs normal/objetivo). IA explicable y silenciosa por defecto. Responsive de primera clase.
9. **Datos modificables primero, UI de edición después** — si falta la pantalla, el valor igual se cambia por seed/código.

---

## 3. Motor financiero — lo más importante, y va con TESTS PRIMERO

Implementa el contrato `contrato-motor-financiero-kpis-prioritarios.md`. **Escribe los tests antes que la UI** y verifícate corriéndolos.

**Dos niveles de cálculo:**

```
NIVEL CUENTA-MES (operativo, sin fee)
  cpl   = inversión / prospectos                 (leads)
  cpa   = inversión / ventas[_concretadas]
  roas  = monto_venta / inversión
  aov   = monto_venta / ventas
  %conv = ventas / prospectos|clics
  utilidad_antes_honorarios = monto_venta × margin_pct − inversión

NIVEL ENGAGEMENT-MES = cliente × plataforma (suma sus cuentas, misma moneda)
  cac           = (ΣAds + honorarios) / Σventas
  utilidad_neta = Σmonto × margin_pct − honorarios − ΣAds
  roi           = (Σmonto × margin_pct) / (ΣAds + honorarios)     ← CANÓNICO
  %anuncios     = Σventas / ventas_totales        (solo si ventas_totales)
```

- `margin_pct`: de `Client` (default 0.35, editable).
- `honorarios`: del engagement (cliente × plataforma), de STATUS.
- `value_source = manual_close` → `ventas`/`monto` solo de captura manual; el proxy de plataforma se ignora.
- `purpose = vacantes` → sin ROI, muestra CPV (`inversión / vacantes`).
- Excepción **Ser Rizada**: panel leads pero `value_source = auto_platform`.

**Test de aceptación (de la plantilla, mes enero leads):** prospectos 509, inversión 500.09, ventas 35, monto 15,800, margen 0.35, honorarios 675, ventas_totales 430 →
`CPL 0.98 · AOV 451.43 · %conv 6.88% · CPA 14.29 · ROAS 31.59 · CAC 33.57 · utilidad_neta 4,354.91 · ROI 4.71 · %anuncios 8.14%`. Incluye también un caso con **ROI negativo** (mes de arranque).

**Cierre de mes** (`is_closed`): congela `margin_pct_snapshot` y `fee_snapshot`; bloquea edición; alimenta `AccountBaseline`. Mes abierto: provisional; leads sin cierres → "pendiente de captura", no cero.

---

## 4. Plan de build por fases

Trabaja **una fase por rama/commit**; el sistema funciona al final de cada una. No intentes todo de golpe (controla el gasto de créditos).

| fase | entrega | "done" |
|---|---|---|
| **0 — scaffold + schema + seed skeleton** *(bloquea todo)* | estructura del repo; modelos de ADR-002; esquema fresco; clients de API (Meta/Google) **portando el comportamiento probado**: ventana de re-escritura de 3 días de Google y los mapeos de campos; seed idempotente conectando fuentes; `.env.example` | la app levanta, el esquema se crea, el seed carga el roster desde la API + mapeo, los tests corren |
| **1 — motor financiero + tests** | las fórmulas de §3 en sus dos niveles | tests verdes y reconcilian con el contrato (incl. ROI negativo) |
| **2 — categorización** | `panel_type`/`capture_method`/`value_source` explícitos de la matriz; `pendiente_de_clasificar` para lo no mapeado | toda cuenta resuelve su `panel_type` del seed; ninguna lo deriva del evento |
| **3 — centro de control** | resumen ejecutivo escaneable (resultado · costo/resultado · ROAS · Δ vs normal, peor-primero), **separado por plataforma**; paneles por tipo (ecommerce: ROAS+embudo; leads: costo/resultado + campos manuales) con anomalías inline; date picker (presets + calendario + comparar); responsive | el mercadólogo ve qué atender en <5s |
| **4 — desglose mensual** | grilla editable (API/manual/calculado) + cierre de mes + el motor de §3; dos referencias (tu normal + objetivo) | rentabilidad por cuenta-mes; el cierre congela margen y fee |
| **5 — alertas críticas + ruteo** | `AccountBaseline` ("tu normal" sobre meses cerrados); motor de alertas (umbrales de Google de Carlos + persistencia 3 días; Meta z-score ~2σ); **solo críticas se empujan**; ruteo por `NotificationPreference` (Irving/Carlos) | anomalías persistidas con estado, ruteadas por persona |
| **6 — ActionLog + medición** | `ActionLog` (cambios de presupuesto con histórico — el que hoy se pierde); `MeasurementProfile` visible (bandera offline=NO) | acción↔resultado cruzable; perfil de medición auditable |
| **7 — después** | reskin de la UI del generador de reportes (el motor actual se mantiene); UIs de edición (margen/objetivos/categorización); niveles de alerta Positivo/Rendimiento; comparación YoY | — |

---

## 5. Seed (ver `especificacion-seed-dito.md`)

Orden idempotente: TeamMember (Irving, Carlos) → Client → Account (de API, enriquecida) → MeasurementProfile → Campaign/CampaignMetric (sync) → **MonthlyHistory histórico** (importa meses cerrados de la base vieja + Sheet KPIs) → MonthlyTarget → AccountBaseline → ActionLog.

Reglas de idempotencia (críticas): upsert por clave estable (`external_account_id`, slug de cliente, `(account,year,month)`); el mapeo se re-aplica, pero `margin_pct`/`fee`/`targets` se escriben **solo si están vacíos** (no pisar ediciones); meses cerrados inmutables; el seed nunca borra (cuentas ausentes → `inactivo`).

Casos límite: multi-ubicación (Multi-Encomiendas, ADN Gym) = N cuentas con `location_label` → un cliente; cuentas en pausa (Escampa, Irona) = `pausado`; Micah's inactivo = `inactivo`; vacantes = `purpose=vacantes`; monedas de la API; margen 0.35 donde falte.

---

## 6. Alcance del día 1

**Sí:** dashboard (resumen + paneles por tipo, por plataforma) sobre el seed; desglose mensual con captura + cierre; alertas **solo críticas** ruteadas; `ActionLog` de presupuestos; "tu normal" donde haya meses cerrados; objetivos sembrados.

**Después:** niveles de alerta Positivo/Rendimiento; reskin del reporte a cliente; UIs de edición; comparación YoY.

La capa operativa queda funcional el día 1 para **todas** las cuentas. La financiera: completa en ecommerce, progresiva en leads (depende de la captura de cierres; el sistema rastrea el % de llenado).

---

## 7. Acuerdo de trabajo

- Commits chicos; cada fase deja el sistema funcionando.
- **Tests del motor financiero antes de tocar UI.**
- Esquema fresco (es build nuevo); el histórico entra por importación/seed, no por migración en sitio.
- Reconstruye el sync limpio pero **preserva su comportamiento probado** (no rediseñes lo que ya funciona).
- `.env` para llaves (Meta/Google/Anthropic); nunca commitearlas.
- Ante cualquier duda no cubierta por `/docs`, **pregunta** en vez de asumir.

---

## Primera tarea

Arranca la **Fase 0**: crea la estructura del repo, define los modelos de ADR-002 en `webapp/models.py`, genera el esquema fresco, arma el esqueleto de los clients de API y del `seed.py` idempotente, y deja `.env.example` + el scaffold de `tests/`. Cuando levante y el seed cargue el roster desde la API, corre los tests y reporta el estado antes de seguir a la Fase 1.

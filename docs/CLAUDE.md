# CLAUDE.md — DITO / SoldaDito

> Memoria del proyecto para Claude Code. Léela completa antes de tocar código. Consolida ADR-001 (refactor) + ADR-002 (modelo final) en reglas operativas.

## Qué es esto

DITO es la **capa analítica y de resultados financieros** sobre las cuentas publicitarias de Meta y Google de la agencia. No reemplaza el CRM (Notion) ni el sync de las APIs: se monta encima y responde, en <5s, *"¿qué cuentas tuvieron algo inusual?"* y *"¿es rentable esta cuenta para el cliente?"*.

**Estamos en un refactor (Vía A): evolucionamos la app Flask que ya corre, no reconstruimos.** El trabajo es modelo de datos + jerarquía de información, no cambio de stack.

## Documentos fuente de verdad (`/docs`)

| documento | qué fija |
|---|---|
| `ADR-001-refactor-dito.md` | refactor, navegación de 4 áreas, principios de arquitectura, fases |
| `ADR-002` (piezas 1–3) | modelo de datos final, categorización, motor financiero, alertas, proceso |
| `DITO-schema-base.md` | schema objetivo y layout |
| `contrato-motor-financiero-kpis-prioritarios.md` | campos y **fórmulas** del desglose (KPIs prioritarios) |
| `matriz-categorizacion-implicaciones-modelo.md` | el tipo de cada cuenta (semilla de `panel_type`) |

Si una decisión no está aquí ni en esos docs, **pregunta antes de inventar**. ADR/schema son append-only: se extienden, no se reescriben.

## Stack

Flask · SQLAlchemy · SQLite (WAL) en `instance/dito.db` · Jinja2 · Bootstrap 5.3 · APScheduler · Flatpickr · API Anthropic (Haiku para triage de anomalías, Sonnet para reportes). Modelos en `webapp/models.py`.

## Modelo de datos (resumen — detalle en ADR-002)

Jerarquía: **TeamMember → Client → Account → (Campaign → CampaignMetric)** con `MonthlyHistory`, `MonthlyTarget`, `AccountBaseline`, `MeasurementProfile`, `Alert`, `ActionLog`.

Deltas clave que introduce ADR-002 sobre el modelo actual:
- `Account.panel_type` (`ecommerce`/`leads`) **explícito**, sembrado de la matriz. Se elimina la derivación "automático".
- `Account.capture_method[]` (`checkout`/`onsite_pixel`/`instant_form`/`messages`/`calls`/`job_applications`) + una `primary`.
- `Account.value_source` (`auto_platform`/`manual_close`) — explícito.
- `Account.currency` desde API; `location_label`; `purpose` (`ventas_leads`/`vacantes`); `assigned_to`.
- `Client.margin_pct` (default 0.35, **editable**), `ticket_tier`, `commercial_tier`, `status` (`activo`/`pausado`/`inactivo`/`baja`), `monthly_fee`.
- Nuevas: `MonthlyTarget` (objetivo vs logrado), `MeasurementProfile`, `AccountBaseline`, `Alert`, `ActionLog`.
- `mensajes` **ya no es un tipo** — es un `capture_method` de `leads`.

## Reglas duras (no negociables)

**Datos y dominio**
1. **Plataformas nunca se suman.** Google y Facebook separados, cada uno su moneda (MXN/USD/COP). El ROI-con-honorarios se calcula a nivel **engagement = cliente × plataforma** (suma ubicaciones, nunca cruza plataformas).
2. **`panel_type` explícito, nunca derivarlo del evento.** Cuenta sin mapeo → `pendiente_de_clasificar`, jamás un tipo asumido.
3. **Valor de leads solo del cierre manual.** Si `value_source = manual_close`, el valor de plataforma (proxy de Smart Bidding) se **ignora** en todo cálculo.
4. **ROI canónico, una sola definición:** `(Valor × margen) / (Ads + honorarios)`. `Utilidad Neta = Valor × margen − Ads − honorarios`.
5. **Margen editable**, default `0.35`. **Nunca hardcodear** — vive en `Client.margin_pct`.
6. **El origen de cada dato varía por campo:** API / manual / calculado / config. Rastrear con `*_source`. Campos API son read-only (badge API).
7. **Sin Notion en vivo.** Todo nativo y sembrado (CSVs STATUS + Google Sheet KPIs). 
8. **Cierre de mes congela** `margin_pct_snapshot` y `fee_snapshot`; cambiar el margen después no altera meses cerrados.

**Arquitectura (de ADR-001)**
9. **Route → Service → Client.** Nunca llamar a la API externa desde una ruta; pasa por el servicio.
10. **Constantes de plataforma, nunca literales** (`PLATFORM_GOOGLE_ADS`, `PLATFORM_FACEBOOK_ADS`).
11. **Migraciones idempotentes.** Nunca `create_all()` sobre columnas existentes. **Cero pérdida de datos** (hay desglose ya capturado en `dito.db`).
12. **CSRF en toda ruta POST** que mute estado.
13. **Un número nunca sin contexto:** valor + delta + vs "tu normal" / objetivo.
14. **IA explicable y silenciosa por defecto** (inline + "por qué", sin saturar).
15. **El sync y los clientes de API no se tocan.**
16. **Responsive de primera clase.**

**Producto**
17. **Datos modificables primero, UI de edición después** (D6). Si falta la pantalla para editar un valor, igual debe poder cambiarse por seed/código.
18. **Día 1:** dashboard + desglose mensual + alertas **solo críticas**. El generador de reportes se mantiene como está; solo se reskinea la UI después.
19. **Equipo: Irving + Carlos.** Ruteo de avisos por `assigned_to` según `NotificationPreference` (Irving: WhatsApp+tablero, semanal, 1 sem; Carlos: tablero+correo, tiempo real, 3 días).

## Flujo de trabajo (para ti, Claude Code)

- **Tareas chicas con criterio de aceptación**, no "refactoriza todo". Orden (reusa fases de ADR-001 §9):
  1. modelo + migración idempotente + **seed**
  2. corrección de clasificación (`panel_type`/`capture_method`/`value_source` desde la matriz)
  3. motor financiero (contrato KPIs) **+ tests**
  4. resumen ejecutivo (tabla peor-primero, por plataforma)
  5. alertas críticas + ruteo
  6. `ActionLog` de presupuestos
  7. (después) reskin de reportes, UIs de edición, niveles de alerta
- **Tests primero en el motor financiero.** Casos conocidos del contrato (incl. el mes con ROI negativo). Verifícate corriendo los tests, no asumas.
- **Seed idempotente** carga: roster (API + mapeo), `panel_type`/`capture`/`value_source` (matriz), márgenes y objetivos (Google Sheet KPIs), fees (STATUS), monedas (API), cuentas en pausa, y los cierres históricos que existan.
- **`.env`** para llaves (Meta/Google/Anthropic); `.env.example` versionado; nunca commitear llaves.
- Commits chicos; el sistema funciona al final de cada fase.

## Comandos

```
make run        # servidor local
make test       # tests (corre el del motor financiero antes de tocar UI)
make lint
make migrate    # migración idempotente, nunca create_all sobre columnas existentes
make seed       # carga/actualiza el seed (idempotente)
```

## Estructura esperada

```
webapp/            modelos, blueprints (routes), services, clients (API), templates, static
migrations/        Alembic / Flask-Migrate
scripts/seed.py    seed idempotente
tests/             unit del motor financiero + integración
docs/              ADR-001, ADR-002 (1–3), schema-base, contrato financiero, matriz
instance/dito.db   SQLite (no se versiona)
```

# Especificación del seed — DITO (build desde cero)

> Qué carga el sistema para estar **funcional desde el segundo 1**, de qué fuente, en qué orden, y cómo se mantiene idempotente. En el build limpio, el seed también **importa el histórico** (no se preserva la base vieja en sitio). Insumo directo del prompt de Claude Code.

---

## 1. Fuentes y qué aporta cada una

| fuente | aporta | naturaleza |
|---|---|---|
| **API Meta + Google** | roster de cuentas conectadas, `external_account_id`, `currency`, `account_status`, campañas y métricas diarias | **verdad** de qué existe |
| **Matriz de categorización** | `panel_type`, `capture_method` (+ primary), `value_source` por cuenta; mapeo cuenta→cliente y ubicación | curado (cuestionarios) |
| **Google Sheet KPIs** | `margin_pct` por cliente, **objetivos** mensuales por métrica, **histórico de cierres** (meses cerrados), % de llenado del doc de leads | seed financiero |
| **Tableros STATUS (CSVs)** | `monthly_fee`, `commercial_tier`, `etapa`, `status` (activo/pausa/inactivo), hipótesis/testing | seed operativo |
| **Cuestionarios Irving/Carlos** | `MeasurementProfile` (pixel/CAPI/GA4/offline/última verif.) | curado |
| **Base vieja `dito.db`** | `monthly_history` cerrado ya capturado (lo que no esté en el Sheet) | importación única |

---

## 2. Orden de carga *(idempotente)*

```
1. TeamMember          Irving, Carlos  (+ NotificationPreference por defecto)
2. Client              de STATUS + KPIs: nombre, business_type, ticket_tier,
                       margin_pct (0.35 si falta), commercial_tier, status, monthly_fee
3. Account             de la API, enriquecida (§3): client_id, panel_type, capture_method,
                       value_source, currency, location_label, purpose, assigned_to, targets, fee
4. MeasurementProfile  de cuestionarios, por cuenta
5. Campaign + CampaignMetric   del sync (diario; corre en marcha)
6. MonthlyHistory (histórico)  importa meses CERRADOS de dito.db + Sheet, con sus
                       datos manuales y margin/fee snapshot del momento
7. MonthlyTarget       de los objetivos del Sheet, por cuenta/mes/métrica
8. AccountBaseline     CALCULADO de los meses cerrados importados ("tu normal")
9. ActionLog (opc.)    cambios de presupuesto / hipótesis históricos de STATUS
```

Cada paso depende del anterior. 1–4 dejan el modelo; 6–8 dejan "tu normal" con historia; 5 mantiene los datos vivos.

---

## 3. Mapeo cuenta → cliente *(el paso delicado)*

1. La API devuelve **todas** las cuentas conectadas con nombres sucios y por ubicación (`Multi Encomiendas Houston`, `RUMA·Dito`, `Poliestirenos de Querétaro`, imperio `Micah's…`).
2. Un **config de mapeo** (curado de la matriz + la tabla por-cuenta del Sheet KPIs) resuelve cada `external_account_id` → `client_id` + `location_label` + `panel_type`/`capture_method`/`value_source`/`purpose`.
3. Cuenta de la API **sin entrada en el config** → se crea con `status = pendiente_de_clasificar` (visible en administración, fuera de la operación). **Nunca se le asume un tipo.**
4. La clave estable es `external_account_id` (de la API), no el nombre. Los nombres cambian; el ID no.

---

## 4. Reglas de idempotencia *(donde nacen los errores tontos)*

- **Re-ejecutable sin duplicar.** Upsert por clave estable: `Account.external_account_id`, `Client` por slug, `MonthlyHistory` por `(account, year, month)`, `MonthlyTarget` por `(account, year, month, metric)`.
- **Estructura se actualiza; datos editados no se pisan.** El mapeo (cuenta→cliente, `panel_type`) se re-aplica en cada corrida. Pero `margin_pct`, `monthly_fee`, `targets` se escriben **solo si están vacíos** (un valor editado en la app no se clobbea — respeta D6).
- **Meses cerrados nunca se sobrescriben.** `is_closed = true` → inmutable, incluido su `margin_pct_snapshot` y `fee_snapshot`.
- **El seed no borra.** Cuentas que desaparecen de la API se marcan `inactivo`, no se eliminan (recuperables).

---

## 5. Casos límite

| caso | manejo |
|---|---|
| **Multi-ubicación** (Multi-Encomiendas: Houston/Dallas/Austin/Louisiana; ADN Gym: 4 suc.) | cada una es un `Account` con `location_label`, todas → mismo `Client`. El engagement (cliente × plataforma) las agrupa para el ROI |
| **Cuentas en pausa** (Escampa, Irona Sports) | `status = pausado`, visibles, fuera de operación, recuperables |
| **Imperio Micah's inactivo** | `status = inactivo` |
| **Vacantes/Hiring** (Gymex, ADN Gym, Sprinkler) | `purpose = vacantes` → sin ROI, muestra CPV; no entra al ROI de ventas |
| **Monedas** | COP (Crespos, ICONA), USD (Multi-Enc, SkyHigh, Micah's), MXN (resto) — todas de la API, nunca se mezclan |
| **Margen faltante** | `0.35` default donde el Sheet no tiene % de Utilidad; editable |
| **Leads sin histórico de cierres** | se importa lo que exista; baseline parcial; se registra el **% de llenado** del doc y se prioriza la captura sin fricción |
| **Ser Rizada** | `panel_type = leads` pero `value_source = auto_platform` (cita pagada on-site) |

---

## 6. Resultado — qué queda funcional el día 1

- **Todas** las cuentas conectadas, mapeadas a su cliente y tipo (o en `pendiente_de_clasificar`), separadas por plataforma.
- Resumen ejecutivo + paneles por tipo con métricas vivas del sync.
- "Tu normal" donde haya meses cerrados importados; objetivos sembrados.
- Desglose mensual listo para captura; ecommerce con ROI completo, leads en progreso.
- Alertas críticas con umbrales de Google; Meta del baseline.
- Honorarios, márgenes, monedas y tiers cargados — editables después por la app.

---

*Seed especificado. Con esto, el último entregable es el **prompt de Claude Code**: un build limpio desde cero que implementa ADR-001 + ADR-002, el contrato financiero y este seed, en el orden de fases, con tests del motor financiero primero.*

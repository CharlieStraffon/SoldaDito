# contrato del motor financiero — KPIs prioritarios

*Derivado de la plantilla real "PLANTILLAS - KPIs PRIORITARIOS" (hojas GENERACIÓN DE LEADS y VENTA DIRECTA), con fórmulas verificadas contra los datos de muestra. Esta es la definición contra la cual se construye el desglose mensual. Si el sistema no reproduce esto exactamente, no es funcional.*

---

## 0. la decisión que cambia el motor actual

El DITO actual calcula `ROI = (valor_ventas − costos) / costos`. **Tu proceso no.** Tu plantilla ajusta por **margen de utilidad (35%)** y expresa varias cosas distinto:

| concepto | DITO actual | **KPIs prioritarios (el correcto)** |
|---|---|---|
| base de rentabilidad | valor de ventas bruto | **ingresos netos = monto × margen** |
| ROI | `(valor − costos)/costos × 100` (%) | **`ingresos_netos / (inversión + honorarios)`** (múltiplo) |
| CAC | no se calcula | **`(inversión + honorarios) / ventas`** |
| utilidad neta | no se calcula | **`monto × margen − honorarios − inversión`** |
| margen | no existe | **campo por cliente, default 35%** |
| % de anuncios | no existe | **`ventas / ventas_totales`** |

→ El motor financiero se reescribe sobre estas fórmulas. Es el cambio más importante del refactor.

---

## 1. estructura común de las dos hojas

Las dos hojas comparten el mismo **bloque financiero** y **bloque general**; solo difiere el **tope del embudo** (tráfico → venta) y el origen de `ventas`/`monto`:

```
[ TRÁFICO ] → [ VENTA ] → [ ANUNCIOS ] → [ FINANCIERO (margen) ] → [ GENERAL ]
   varía       varía         común             común                  común
```

Esto es clave para el schema: **un núcleo financiero único** + un **tope específico por tipo**. No son dos motores; es uno con dos entradas.

---

## 2. hoja LEADS / SERVICIOS — campos, origen y fórmula

| campo | bloque | origen | fórmula |
|---|---|---|---|
| `mes` | — | sistema | período |
| `prospectos` | tráfico | **API** | mensajes / leads / llamadas según `capture_method` |
| `cpl` | tráfico | calculado | `inversión / prospectos` |
| `ventas_concretadas` | venta | **MANUAL** | captura del equipo (cierre) |
| `monto_venta` | venta | **MANUAL** | captura del equipo |
| `aov` | venta | calculado | `monto_venta / ventas_concretadas` |
| `pct_conversion_clientes` | venta | calculado | `ventas_concretadas / prospectos` |
| `inversion` | anuncios | **API** | gasto de la cuenta |
| `cpa` | anuncios | calculado | `inversión / ventas_concretadas` |
| `roas` | anuncios | calculado | `monto_venta / inversión` |
| `margen` | financiero | **MANUAL** (default 35%) | por cliente |
| `honorarios` | financiero | **DB (ex-Notion)** | fee del cliente, congelado al cerrar mes |
| `cac` | financiero | calculado | `(inversión + honorarios) / ventas_concretadas` |
| `utilidad_neta` | financiero | calculado | `monto_venta × margen − honorarios − inversión` |
| `roi` | financiero | calculado | `(monto_venta × margen) / (inversión + honorarios)` |
| `ventas_totales` | general | **MANUAL** (opcional) | total del negocio, lo da el cliente |
| `pct_anuncios` | general | calculado | `ventas_concretadas / ventas_totales` |

**Verificación (enero 2026 de la plantilla):** prospectos 509, inversión $500.09, ventas 35, monto $15,800, margen 35%, honorarios $675 →
CPL $0.98 · AOV $451.43 · %conv 6.88% · CPA $14.29 · ROAS 31.59 · CAC $33.57 · utilidad $4,354.91 · ROI 4.71 · %anuncios (430 totales) 8.14%. ✓ Todo cuadra.

---

## 3. hoja VENTA DIRECTA / ECOMMERCE — campos, origen y fórmula

Mismo bloque financiero y general. Cambia el tope: embudo de tráfico + `ventas`/`monto` vienen de la **API** (el pixel ve la compra y su valor), no manual.

| campo | bloque | origen | fórmula |
|---|---|---|---|
| `clics` | tráfico | **API** | — |
| `add_to_carts` | tráfico | **API** | — |
| `checkout` | tráfico | **API** | — |
| `ventas` | venta | **API** | compras del pixel |
| `monto_venta` | venta | **API** | valor de compras del pixel |
| `aov` | venta | calculado | `monto_venta / ventas` |
| `pct_conversion_clientes` | venta | calculado | `ventas / clics` |
| `inversion` | anuncios | **API** | gasto |
| `cpa` | anuncios | calculado | `inversión / ventas` |
| `roas` | anuncios | calculado | `monto_venta / inversión` |
| `margen` · `honorarios` · `cac` · `utilidad_neta` · `roi` | financiero | igual que leads | *(idénticas a §2)* |
| `ventas_totales` · `pct_anuncios` | general | manual / calculado | `ventas / ventas_totales` |

**Diferencia de origen vs leads:** en ecommerce `ventas` y `monto_venta` son **API** (read-only, badge API). En leads son **MANUAL**. Esto es lo que `value_source` codifica: `auto_platform` (ecommerce) vs `manual_close` (leads).

> **Excepción Ser Rizada:** lead con pago on-site → `value_source = auto_platform` aunque sea panel leads. El campo es explícito justo para este caso.

---

## 4. mapeo al schema (`monthly_history` extendido)

La tabla `monthly_history` actual se extiende para cubrir el contrato. Campos por origen:

- **API (read-only, badge API):** `inversion`; ecommerce: `clics, add_to_carts, checkout, ventas, monto_venta`; leads: `prospectos`.
- **MANUAL (captura del equipo):** leads: `ventas_concretadas, monto_venta`; ambos: `ventas_totales`; `margen` (default 35%, override por cliente).
- **DB / ex-Notion (congelado al cerrar):** `honorarios` (del campo fee del cliente).
- **CALCULADO (solo lectura):** `cpl, aov, pct_conversion, cpa, roas, cac, utilidad_neta, roi, pct_anuncios`.
- **Estado:** `is_closed` (botón "Cerrar mes"); al cerrar, congela `honorarios` y `margen` y bloquea edición.

Regla de integridad (evita reintroducir el bug):
- Si `panel_type = leads` y `value_source = manual_close` → `ventas`/`monto` **nunca** se leen de la API; el valor-proxy de plataforma se ignora para todo cálculo financiero.
- `pct_anuncios` solo se muestra si `ventas_totales` está capturado; si no, queda oculto (no `n/a` ruidoso).
- Mensajes sin cierre (valor-cero real, hoy inexistente) → `roi = NULL`, solo volumen + costo/conversación.

---

## 5. lo que esto implica para el "tu normal" y las alertas

- **"Tu normal"** se calcula sobre los **meses cerrados** (igual que hoy), pero ahora sobre las métricas del contrato (CPA, ROAS, CAC, ROI-múltiplo, costo/resultado).
- Las **alertas de Google** (umbrales de Carlos) corren sobre estas mismas métricas: CPA +25%, CPL +23%, ROAS −45%, gasto ±30%, conversiones −28%, IS perdido >12%/5d, 60 clics sin conv. — persistencia 3 días.

---

*Este contrato es el corazón de "funcional según KPIs prioritarios". El ADR lo referencia y el schema lo implementa campo por campo.*

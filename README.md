# DITO / SoldaDito

Capa analítica y de resultados financieros sobre las cuentas de Meta y Google de la agencia.
North star: responder en <5s *"¿qué cuentas tuvieron algo inusual?"* y *"¿es rentable esta cuenta?"*.

Stack: Flask · SQLAlchemy · SQLite (WAL) · Jinja2 · Bootstrap 5.3 · APScheduler · Flatpickr ·
Anthropic (Haiku triage / Sonnet reportes). Patrón **Route → Service → Client**.

## Arranque

```bash
make install        # venv + dependencias core
make schema         # crea el esquema fresco (greenfield)
make seed           # roster (API o fallback dito.db legacy) + matriz + STATUS + métricas
make run            # http://127.0.0.1:5000
make test           # suite (motor financiero primero)
make diag           # diagnóstico: esquema + seed idempotente + categorización + boot
```

Para sync en vivo contra Meta/Google: `.venv/bin/pip install -r requirements-sync.txt` y llaves en `.env`.

## Áreas (fases)

| ruta | qué |
|---|---|
| `/` | Centro de control: resumen ejecutivo peor-primero, **por plataforma**, Δ vs normal, pendientes aparte |
| `/accounts/<id>` | Detalle por tipo (ecommerce embudo / leads costo-resultado), tendencia, alertas inline, acciones, medición |
| `/desglose` | Desglose mensual editable + cierre de mes (congela margen/fee) + KPIs de engagement |
| `/alertas` | Alertas (solo críticas se empujan) ruteadas por persona (Irving/Carlos) |
| `/acciones` | ActionLog: presupuestos con histórico + hipótesis |
| `/admin` | Reclasificar pendientes, editar margen/objetivos/fees |
| `/reportes` | Reporte por engagement-mes con MoM/YoY + narrativa Sonnet |

## Reglas duras (ADR-002)

- Plataformas **nunca se suman**; ROI a nivel **engagement = cliente × plataforma**, cada uno su moneda.
- `panel_type` **explícito** (sembrado de la matriz), nunca derivado del evento.
- Valor de leads **solo del cierre manual** (`value_source=manual_close`); excepción Ser Rizada (auto).
- **ROI canónico** `(Σmonto × margen)/(ΣAds + honorarios)`. Margen editable, default 0.35.
- Cierre de mes congela `margin_pct_snapshot`/`fee_snapshot`. CSRF en todo POST mutante.
- Honorarios se cuentan **una vez** por engagement (no por cuenta — evita doble-conteo multi-ubicación).

Docs fuente de verdad en `docs/`. El histórico entra por seed (no migración en sitio).

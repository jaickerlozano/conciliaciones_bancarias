# Conciliaciones Bancarias — Gaudi Administraciones

Genera la conciliación bancaria mensual de cada comunidad a partir de las planillas de
ingresos y egresos y de la cartola del banco.

Reglas del proyecto, stack y comandos: ver [AGENTS.md](AGENTS.md).

## Inicio rápido (motor, fase 1)

```bash
cd backend
uv sync
uv run pytest
```

Los tests con archivos reales del cliente buscan los datos en `../ingresos_egresos_cartolas/`
(o en `$CONCILIACION_DATOS_DIR`) y se omiten si no están.

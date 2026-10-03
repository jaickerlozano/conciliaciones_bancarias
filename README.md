# Conciliaciones Bancarias — Gaudi Administraciones

Genera la conciliación bancaria mensual de cada comunidad a partir de las planillas de
ingresos y egresos y de la cartola del banco.

Reglas del proyecto, stack y comandos: ver [AGENTS.md](AGENTS.md).

## Inicio rápido

Requisitos: Docker Desktop, [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env
docker compose up -d db            # PostgreSQL 16 en localhost:5432

cd backend
uv sync
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py demo_cinema   # opcional: carga el piloto con datos reales
uv run python manage.py runserver     # http://localhost:8000/admin
uv run pytest
```

Los tests y el comando `demo_cinema` buscan los archivos reales del cliente en
`../ingresos_egresos_cartolas/` (o en `$CONCILIACION_DATOS_DIR`); los tests se omiten si no están.

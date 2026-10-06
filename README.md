# Conciliaciones Bancarias — Gaudi Administraciones

Genera la conciliación bancaria mensual de cada comunidad a partir de las planillas de
ingresos y egresos y de la cartola del banco.

Reglas del proyecto, stack y comandos: ver [AGENTS.md](AGENTS.md).

## Inicio rápido

Requisitos: Docker Desktop, [uv](https://docs.astral.sh/uv/), Node 24 + pnpm.

```bash
cp .env.example .env
docker compose up -d db            # PostgreSQL 16 en localhost:5433

cd backend
uv sync
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py cargar_piloto cinema   # opcional: pilotos con datos reales (cinema | bustos)
uv run python manage.py runserver     # API en :8010 (admin técnico en /admin)
uv run pytest

cd ../frontend
pnpm install
pnpm dev                              # panel en http://localhost:5180
```

Los tests y el comando `cargar_piloto` buscan los archivos reales del cliente en
`../ingresos_egresos_cartolas/` y `../bustos/` (o en `$CONCILIACION_DATOS_DIR` / `$CONCILIACION_BUSTOS_DIR`); los tests se omiten si no están.

This directory stores Alembic revision scripts.

To create the initial migration (autogenerate), run from repository root:

```bash
cd backend
alembic -c alembic.ini revision --autogenerate -m "initial"
alembic -c alembic.ini upgrade head
```

If you don't have `alembic` installed in your environment, install it with:

```bash
pip install alembic
```

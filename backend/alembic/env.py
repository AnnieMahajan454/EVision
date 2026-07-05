from __future__ import with_statement
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# make project root importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import the project's metadata (Base) so autogenerate can detect models
from backend.database.base import Base  # noqa: E402

# ensure models are imported so they register with Base.metadata
import pkgutil
import backend.models
for _, name, _ in pkgutil.iter_modules(backend.models.__path__):
    __import__(f"backend.models.{name}")

target_metadata = Base.metadata


def get_url():
    return os.environ.get('DATABASE_URL', 'sqlite:///./dev.db')


def run_migrations_offline():
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    configuration = config.get_section(config.config_ini_section)
    configuration['sqlalchemy.url'] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

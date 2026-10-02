"""Opt-in PostgreSQL tests using the same POSTGRES_* / DATABASE_URL configuration.

Requires permission to create a separate test database. Never uses keepdb.
"""
from copy import deepcopy

from .test import *  # noqa: F403
from .base import DATABASES as APPLICATION_DATABASES

DATABASES = deepcopy(APPLICATION_DATABASES)
DATABASES["default"]["CONN_MAX_AGE"] = 0
DATABASES["default"]["OPTIONS"] = {"connect_timeout": 3}

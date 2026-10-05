"""PostgreSQL/PostGIS tests using the same POSTGRES_* / DATABASE_URL configuration.

Requires permission to create a separate test database. Never uses keepdb.
"""
from copy import deepcopy
import os

from .test import *  # noqa: F403
from .base import DATABASES as APPLICATION_DATABASES

DATABASES = deepcopy(APPLICATION_DATABASES)
DATABASES["default"]["CONN_MAX_AGE"] = 0
DATABASES["default"]["OPTIONS"] = {"connect_timeout": 3}

POSTGRES_TEST_TEMPLATE = os.getenv("POSTGRES_TEST_TEMPLATE", "")
if POSTGRES_TEST_TEMPLATE:
    DATABASES["default"].setdefault("TEST", {})["TEMPLATE"] = POSTGRES_TEST_TEMPLATE

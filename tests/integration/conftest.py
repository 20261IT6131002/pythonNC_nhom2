"""Mongo fixtures only own and drop freshly generated test databases."""

import os
from uuid import uuid4

import pytest

from noteapp.domain.errors import RepositoryUnavailable
from noteapp.infrastructure.config import Config
from noteapp.infrastructure.mongo.client import create_client, ping
from noteapp.infrastructure.mongo.indexes import create_indexes


@pytest.fixture
def mongo_database():
    uri = os.environ.get("NOTEAPP_TEST_MONGO_URI")
    required = os.environ.get("NOTEAPP_REQUIRE_MONGO") == "1"
    if not uri:
        if required:
            pytest.fail("NOTEAPP_TEST_MONGO_URI is required for integration.")
        pytest.skip("Integration needs an isolated NOTEAPP_TEST_MONGO_URI.")
    requested_name = os.environ.get("NOTEAPP_TEST_DB_NAME", "noteapp_test_run")
    Config(uri, requested_name, 2000)
    if not requested_name.startswith("noteapp_test_"):
        pytest.fail("Integration database names must have the noteapp_test_ prefix.")
    owned_name = requested_name + "_" + uuid4().hex
    config = Config(uri, owned_name, 2000)
    client = create_client(config)
    try:
        try:
            ping(client)
        except RepositoryUnavailable:
            if required:
                pytest.fail("Required isolated Mongo is unavailable.")
            pytest.skip("Isolated Mongo is unavailable; no database was touched.")
        database = client[owned_name]
        create_indexes(database)
        try:
            yield database, config
        finally:
            assert owned_name.startswith("noteapp_test_") and owned_name == config.db_name
            client.drop_database(owned_name)
    finally:
        client.close()

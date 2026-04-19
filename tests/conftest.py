import pytest
from pathlib import Path
from devwatcher.db import get_db, init_db

@pytest.fixture
def tmp_db(tmp_path):
    conn = get_db(db_path=tmp_path / "test.sqlite")
    init_db(conn)
    return conn

@pytest.fixture
def tmp_config_path(tmp_path):
    return tmp_path / "config.toml"

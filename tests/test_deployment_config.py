import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize("scheme", ["postgresql", "postgres"])
def test_postgres_provider_url_uses_installed_driver(scheme):
    environment = {**os.environ, "DATABASE_URL": f"{scheme}://user:password@localhost:5432/tracker"}
    result = subprocess.run(
        [sys.executable, "-c", "from core.database import engine; assert engine.dialect.driver == 'psycopg'"],
        env=environment, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr

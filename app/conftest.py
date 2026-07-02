import os
import tempfile

import pytest

# Must be set before `app` is imported anywhere, since app.py builds its
# SQLAlchemy engine from this env var at import time.
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"

from app import app as flask_app  # noqa: E402


@pytest.fixture()
def client():
    flask_app.config.update(TESTING=True)
    with flask_app.test_client() as test_client:
        yield test_client

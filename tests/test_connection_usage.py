"""Guards against a caller left behind when get_connection became pooled.

`get_connection()` used to return a raw connection; it now returns a context
manager. The conversion updated every call site inside storage.py but missed
seed/seed_demo_corpus.py, which still did `conn = get_connection()` and then
`conn.cursor()` -- failing only when that script was actually run, against a
real database, which happened for the first time mid-deployment.

The static check below catches the same mistake anywhere in the repo.
"""

import pathlib
import re
from unittest.mock import MagicMock

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
SOURCE_DIRS = ("app", "seed", "eval", "tests")


def python_files():
    """Every source file except this one, which quotes the bad pattern in prose."""
    here = pathlib.Path(__file__).resolve()
    for directory in SOURCE_DIRS:
        for path in (REPO / directory).rglob("*.py"):
            if path.resolve() != here:
                yield path


def test_no_module_treats_get_connection_as_a_raw_connection():
    """It is a context manager: `with get_connection() as conn`, never assigned."""
    offenders = []
    for path in python_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"=\s*get_connection\s*\(", line):
                offenders.append(f"{path.relative_to(REPO)}:{lineno}: {line.strip()}")

    assert not offenders, (
        "get_connection() returns a context manager; assigning it yields a "
        "_GeneratorContextManager with no .cursor()/.close():\n  "
        + "\n  ".join(offenders)
    )


def test_get_connection_is_a_context_manager():
    from app.services import storage

    assert hasattr(storage.get_connection, "__wrapped__"), (
        "get_connection should be decorated with @contextmanager"
    )


def test_seed_script_runs_against_a_mocked_connection(monkeypatch):
    """Exercises the seed path without a database or an API call.

    This is the test that would have caught the deployment failure: the script
    had never been executed since the pooling change.
    """
    import seed.seed_demo_corpus as seeder

    cursor = MagicMock()
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor

    class FakeConnCtx:
        def __enter__(self):
            return conn

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(seeder, "get_connection", lambda: FakeConnCtx())
    monkeypatch.setattr(seeder, "embed_chunks", lambda chunks: [[0.0] * 4 for _ in chunks])

    count = seeder.seed()

    assert count > 0
    conn.commit.assert_called_once()
    # One DELETE for the demo document, then one INSERT per chunk.
    statements = [c.args[0].strip().split()[0].upper() for c in cursor.execute.call_args_list]
    assert statements[0] == "DELETE"
    assert statements.count("INSERT") == count


@pytest.mark.parametrize("module", ["seed.seed_demo_corpus", "seed.cleanup_sessions"])
def test_scripts_import_cleanly(module):
    __import__(module)

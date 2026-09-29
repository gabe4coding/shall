import sqlite3
from contextlib import contextmanager


@contextmanager
def conn():
    """A connection whose transaction is committed when the block ends without an error."""
    c = sqlite3.connect("app.db")
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()

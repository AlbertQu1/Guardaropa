import os
from contextlib import contextmanager

import psycopg2
from dotenv import load_dotenv
from pgvector.psycopg2 import register_vector

load_dotenv()


@contextmanager
def conexion():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    register_vector(conn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

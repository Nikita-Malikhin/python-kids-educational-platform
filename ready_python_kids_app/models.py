import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', '127.0.0.1'),
        port=os.getenv('DB_PORT', '5432'),
        dbname=os.getenv('DB_NAME', 'informatics_site'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', 'postgres'),
    )


def query(sql, params=None, one=False, commit=False):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params or ())
        data = cur.fetchall() if cur.description else None
        command = sql.lstrip().split(None, 1)[0].lower()
        if commit or command in {'insert', 'update', 'delete', 'alter', 'create', 'drop'}:
            conn.commit()
        cur.close()
        if one and data:
            return data[0]
        return data
    finally:
        conn.close()


def ensure_schema():
    statements = [
        "ALTER TABLE answers ADD COLUMN IF NOT EXISTS hint TEXT",
        """CREATE TABLE IF NOT EXISTS homework_tasks (
            homework_id SERIAL PRIMARY KEY,
            lecture_id INT NOT NULL REFERENCES lectures(lecture_id) ON DELETE CASCADE,
            level VARCHAR(20) NOT NULL CHECK (level IN ('Junior','Middle','Senior')),
            title VARCHAR(255) NOT NULL,
            description TEXT NOT NULL,
            expected_answer VARCHAR(255) NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS homework_results (
            homework_result_id SERIAL PRIMARY KEY,
            homework_id INT NOT NULL REFERENCES homework_tasks(homework_id) ON DELETE CASCADE,
            user_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            answer TEXT NOT NULL,
            is_correct BOOLEAN NOT NULL,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT unique_user_homework UNIQUE (homework_id, user_id)
        )"""
    ]
    for statement in statements:
        query(statement, commit=True)
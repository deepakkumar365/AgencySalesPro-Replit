"""
Runner to drop ASP_vehicles table using DATABASE_URL env var.
Backups should already exist in migrations/backups/.
"""
import os
import sys
from urllib.parse import urlparse

import psycopg2


def get_conn():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise SystemExit('ERROR: DATABASE_URL not set in environment')
    result = urlparse(database_url)
    params = {
        'dbname': result.path.lstrip('/'),
        'user': result.username,
        'password': result.password,
        'host': result.hostname,
        'port': result.port or 5432
    }
    return psycopg2.connect(**params)


def run():
    print('About to DROP TABLE IF EXISTS "ASP_vehicles" CASCADE;')
    confirm = input('This is destructive. Have you backed up ASP_vehicles? Type YES to proceed: ')
    if confirm != 'YES':
        print('Aborted by user.')
        return

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute('DROP TABLE IF EXISTS "ASP_vehicles" CASCADE;')
        conn.commit()
        print('Dropped table ASP_vehicles (if it existed).')
    except Exception as e:
        conn.rollback()
        print('Error while dropping table:', e)
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    run()

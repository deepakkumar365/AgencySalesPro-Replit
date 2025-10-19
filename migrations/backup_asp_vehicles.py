"""
Backup script for ASP_vehicles table.
Creates CSV and SQL INSERT backup files in migrations/backups/ with a timestamp.
Uses DATABASE_URL environment variable.
"""
import os
import csv
import datetime
from urllib.parse import urlparse

import psycopg2
from psycopg2.extras import RealDictCursor


def get_conn():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise RuntimeError('DATABASE_URL not set in environment')
    result = urlparse(database_url)
    params = {
        'dbname': result.path.lstrip('/'),
        'user': result.username,
        'password': result.password,
        'host': result.hostname,
        'port': result.port or 5432
    }
    return psycopg2.connect(**params)


def backup():
    ts = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    out_dir = os.path.join(os.path.dirname(__file__), 'backups')
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, f'ASP_vehicles_backup_{ts}.csv')
    sql_path = os.path.join(out_dir, f'ASP_vehicles_backup_{ts}.sql')

    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('SELECT * FROM "ASP_vehicles";')
        rows = cur.fetchall()
        if not rows:
            print('No rows found in ASP_vehicles; created empty backups')
        # Write CSV
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            if rows:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                for r in rows:
                    writer.writerow(r)
            else:
                f.write('')
        print(f'CSV backup written to: {csv_path}')

        # Write SQL (CREATE TABLE + INSERTs)
        # Capture CREATE TABLE via information_schema
        cur.execute("SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name='ASP_vehicles' ORDER BY ordinal_position;")
        cols = cur.fetchall()
        if cols:
            # Create a simplistic CREATE TABLE statement (types may be generic)
            create_cols = []
            for c in cols:
                nullable = '' if c['is_nullable']=='NO' else 'NULL'
                create_cols.append(f'"{c["column_name"]}" {c["data_type"]} {nullable}')
            create_stmt = f'-- Table structure for ASP_vehicles\nCREATE TABLE IF NOT EXISTS "ASP_vehicles" (\n  ' + ',\n  '.join(create_cols) + '\n);\n\n'
        else:
            create_stmt = '-- No column metadata found for ASP_vehicles\n'

        with open(sql_path, 'w', encoding='utf-8') as f:
            f.write(create_stmt)
            if rows:
                for r in rows:
                    cols = ', '.join([f'"{k}"' for k in r.keys()])
                    vals = ', '.join([sql_literal(v) for v in r.values()])
                    f.write(f'INSERT INTO "ASP_vehicles" ({cols}) VALUES ({vals});\n')
        print(f'SQL backup written to: {sql_path}')
    finally:
        conn.close()


def sql_literal(v):
    if v is None:
        return 'NULL'
    if isinstance(v, bool):
        return 'TRUE' if v else 'FALSE'
    if isinstance(v, (int, float)):
        return str(v)
    # For strings and dates
    s = str(v).replace("'", "''")
    return f"'{s}'"


if __name__ == '__main__':
    try:
        backup()
    except Exception as e:
        print('Backup failed:', e)
        raise

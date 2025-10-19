#!/usr/bin/env python3
"""
Safely remove vehicle_id column from ASP_work_orders for PostgreSQL.
This script connects directly to the DB using DATABASE_URL from .env
and performs the following (safe) steps:
 - Finds and drops any constraints on ASP_work_orders(vehicle_id)
 - Drops the vehicle_id column if it exists

Run: python migrations\run_remove_workorder_vehicle_id.py
"""

import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

DB_URL = os.environ.get('DATABASE_URL')
if DB_URL and DB_URL.startswith('postgres://'):
    DB_URL = DB_URL.replace('postgres://', 'postgresql://', 1)

SQL_CHECK_COLUMN = """
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'ASP_work_orders' AND column_name = 'vehicle_id'
"""

SQL_FIND_CONSTRAINTS = """
SELECT con.conname
FROM pg_constraint con
JOIN pg_class rel ON rel.oid = con.conrelid
JOIN pg_attribute att ON att.attrelid = rel.oid AND att.attnum = ANY(con.conkey)
WHERE rel.relname = 'ASP_work_orders' AND att.attname = 'vehicle_id'
"""

try:
    if not DB_URL:
        raise SystemExit('ERROR: DATABASE_URL not set in environment')

    print('Connecting to database...')
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    cur = conn.cursor()

    # Check if column exists
    cur.execute(SQL_CHECK_COLUMN)
    if not cur.fetchone():
        print('Column ASP_work_orders.vehicle_id does not exist. Nothing to do.')
        cur.close()
        conn.close()
        raise SystemExit(0)

    # Find constraints that reference vehicle_id
    cur.execute(SQL_FIND_CONSTRAINTS)
    constraints = cur.fetchall()
    if constraints:
        print('Found constraints on vehicle_id:')
        for (cname,) in constraints:
            print(' -', cname)
            try:
                cur.execute(f'ALTER TABLE "ASP_work_orders" DROP CONSTRAINT IF EXISTS "{cname}"')
                print(f'   Dropped constraint {cname}')
            except Exception as e:
                print(f'   Failed to drop constraint {cname}: {e}')
    else:
        print('No constraints found referencing ASP_work_orders(vehicle_id)')

    # Finally drop the column
    try:
        cur.execute('ALTER TABLE "ASP_work_orders" DROP COLUMN IF EXISTS vehicle_id')
        print('Dropped column vehicle_id from ASP_work_orders')
    except Exception as e:
        print('Failed to drop column vehicle_id:', e)
        conn.rollback()
        cur.close()
        conn.close()
        raise

    conn.commit()
    cur.close()
    conn.close()
    print('Migration completed successfully')

except Exception as exc:
    print('ERROR during migration:', str(exc))
    raise

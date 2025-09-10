-- Cautious migration to remove legacy Product.agency_id usage
-- 1) Create backup column if agency_id exists
-- Note: SQLite does not support many ALTERs; prefer Postgres/MySQL in prod.

-- Example Postgres-safe approach (commented if not needed):
-- ALTER TABLE ASP_products RENAME COLUMN agency_id TO agency_id_legacy;

-- If you actually have ASP_products.agency_id, consider dropping foreign key constraints and the column after verifying all references are migrated.
-- ALTER TABLE ASP_products DROP COLUMN agency_id;

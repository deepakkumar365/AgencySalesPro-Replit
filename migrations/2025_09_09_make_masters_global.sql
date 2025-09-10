-- Make Category, UOM, TaxMaster global (remove agency_id)
-- PostgreSQL version with quoted identifiers to match existing table names

BEGIN;

-- Drop agency_id columns (with CASCADE to remove dependent constraints/indexes)
ALTER TABLE "ASP_categories" DROP COLUMN IF EXISTS agency_id CASCADE;
ALTER TABLE "ASP_uoms" DROP COLUMN IF EXISTS agency_id CASCADE;
ALTER TABLE "ASP_tax_masters" DROP COLUMN IF EXISTS agency_id CASCADE;

COMMIT;

BEGIN;

-- 1) If the column exists, first rename it (keeps data for backfill)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = 'ASP_products' AND column_name = 'agency_id'
  ) THEN
    ALTER TABLE "ASP_products" RENAME COLUMN agency_id TO agency_id_legacy;
  END IF;
END$$;

-- 2) Ensure the legacy column is nullable
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = 'ASP_products' AND column_name = 'agency_id_legacy'
  ) THEN
    ALTER TABLE "ASP_products" ALTER COLUMN agency_id_legacy DROP NOT NULL;
  END IF;
END$$;

-- 3) Backfill ProductAgency mappings from the legacy data
INSERT INTO "ASP_product_agencies" (product_id, agency_id, is_active, created_at)
SELECT p.id, p.agency_id_legacy, TRUE, NOW()
FROM "ASP_products" p
WHERE p.agency_id_legacy IS NOT NULL
ON CONFLICT (product_id, agency_id) DO NOTHING;

-- 4) Drop any FK referencing the legacy column, then drop it
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'ASP_products' AND column_name = 'agency_id_legacy'
  ) THEN
    -- Try to drop potential FK gracefully if it exists
    BEGIN
      ALTER TABLE "ASP_products" DROP CONSTRAINT IF EXISTS "ASP_products_agency_id_fkey";
    EXCEPTION WHEN undefined_object THEN
      -- ignore
      NULL;
    END;
    ALTER TABLE "ASP_products" DROP COLUMN agency_id_legacy;
  END IF;
END$$;

COMMIT;

ALTER TABLE "ASP_products" ALTER COLUMN agency_id DROP NOT NULL;

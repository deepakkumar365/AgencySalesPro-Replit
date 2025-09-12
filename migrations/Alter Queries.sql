BEGIN;

ALTER TABLE "ASP_products"
  DROP COLUMN IF EXISTS price,
  DROP COLUMN IF EXISTS cost,
  DROP COLUMN IF EXISTS stock_quantity,
  DROP COLUMN IF EXISTS category,
  DROP COLUMN IF EXISTS uom,
  DROP COLUMN IF EXISTS tax_rate,
  DROP COLUMN IF EXISTS tax_code;

COMMIT;


SELECT column_name
FROM information_schema.columns
WHERE table_name = 'ASP_products'
ORDER BY column_name;

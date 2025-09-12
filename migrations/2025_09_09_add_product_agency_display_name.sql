-- Add display_name to ASP_product_agencies if not exists
ALTER TABLE ASP_product_agencies ADD COLUMN IF NOT EXISTS display_name VARCHAR(150);

-- Optional: backfill display_name with product name for readability (Postgres syntax)
-- UPDATE ASP_product_agencies pa
-- SET display_name = p.name
-- FROM ASP_products p
-- WHERE pa.product_id = p.id AND pa.display_name IS NULL;
-- Add buy_price and mrp_price to ASP_product_agencies (idempotent for Postgres)
ALTER TABLE "ASP_product_agencies" ADD COLUMN IF NOT EXISTS buy_price NUMERIC(10,2);
ALTER TABLE "ASP_product_agencies" ADD COLUMN IF NOT EXISTS mrp_price NUMERIC(10,2);

-- Note: SQLite does not support IF NOT EXISTS for ADD COLUMN in older versions.
-- For SQLite, run the following (will fail safely if column exists in newer SQLite):
-- ALTER TABLE ASP_product_agencies ADD COLUMN buy_price NUMERIC(10,2);
-- ALTER TABLE ASP_product_agencies ADD COLUMN mrp_price NUMERIC(10,2);
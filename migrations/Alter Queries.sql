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

-- 1. Add the new integer column to the agency table.
ALTER TABLE "ASP_agencies" ADD COLUMN agency_manager_id INTEGER;

-- 2. Add a foreign key constraint to link it to the users table.
-- This ensures data integrity. ON DELETE SET NULL will set the manager to NULL
-- if the manager's user account is ever deleted.
ALTER TABLE "ASP_agencies"
ADD CONSTRAINT fk_agency_manager_user
FOREIGN KEY (agency_manager_id)
REFERENCES "ASP_users" (id)
ON DELETE SET NULL;

-- 3. Create an index on the new column for faster lookups when
-- searching for an agency by its manager.
CREATE INDEX ix_asp_agencies_agency_manager_id ON "ASP_agencies" (agency_manager_id);


ALTER TABLE "ASP_suppliers" ADD COLUMN notes TEXT;

ALTER TABLE "ASP_purchase_orders" ADD COLUMN IF NOT EXISTS location_id INTEGER;
ALTER TABLE "ASP_purchase_orders"
    ADD CONSTRAINT IF NOT EXISTS fk_po_location FOREIGN KEY (location_id)
        REFERENCES "ASP_locations" (id) ON DELETE SET NULL;

-- First add the column
ALTER TABLE "ASP_subscriptions" 
ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Then create a function to update the timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Finally, create the trigger
CREATE TRIGGER update_asp_subscriptions_updated_at 
BEFORE UPDATE ON "ASP_subscriptions" 
FOR EACH ROW 
EXECUTE FUNCTION update_updated_at_column();

-- Add the column
ALTER TABLE "ASP_subscription_items" 
ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Optional: Update existing rows to have the current timestamp
UPDATE "ASP_subscription_items" 
SET created_at = CURRENT_TIMESTAMP 
WHERE created_at IS NULL;


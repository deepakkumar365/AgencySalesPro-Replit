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

-- Add Foreign Key to ASP_customers table
ALTER TABLE "ASP_subscriptions" 
ADD CONSTRAINT "ASP_subscriptions_customer_id_fkey" 
FOREIGN KEY (customer_id) 
REFERENCES "ASP_customers" (id);

-- Add Unique Constraint
ALTER TABLE "ASP_subscriptions" 
ADD CONSTRAINT "ASP_subscriptions_customer_id_key" 
UNIQUE (customer_id);

-- Create Index
CREATE INDEX "ix_ASP_subscriptions_customer_id" 
ON "ASP_subscriptions" (customer_id);


ALTER TABLE "ASP_subscriptions" ALTER COLUMN agency_id DROP NOT NULL;

ALTER TABLE "ASP_subscriptions" ALTER COLUMN customer_id DROP NOT NULL;

ALTER TABLE "ASP_subscription_invoices" 
ADD COLUMN customer_id INTEGER,
ADD CONSTRAINT "ASP_subscription_invoices_customer_id_fkey" FOREIGN KEY (customer_id) REFERENCES "ASP_customers" (id);

CREATE INDEX "ix_ASP_subscription_invoices_customer_id" ON "ASP_subscription_invoices" (customer_id);



-- Add the agency_id column to the inventory transactions table
ALTER TABLE "ASP_inventory_transactions" ADD COLUMN agency_id INTEGER;

-- Add the customer_id column to the inventory transactions table
ALTER TABLE "ASP_inventory_transactions" ADD COLUMN customer_id INTEGER;

-- Add a foreign key constraint to link agency_id to the agencies table
ALTER TABLE "ASP_inventory_transactions" ADD CONSTRAINT fk_inventory_transactions_agency_id FOREIGN KEY (agency_id) REFERENCES "ASP_agencies" (id);

-- Add a foreign key constraint to link customer_id to the customers table
ALTER TABLE "ASP_inventory_transactions" ADD CONSTRAINT fk_inventory_transactions_customer_id FOREIGN KEY (customer_id) REFERENCES "ASP_customers" (id);

-- Create an index on the new agency_id column for faster lookups
CREATE INDEX ix_ASP_inventory_transactions_agency_id ON "ASP_inventory_transactions" (agency_id);

-- Create an index on the new customer_id column for faster lookups
CREATE INDEX ix_ASP_inventory_transactions_customer_id ON "ASP_inventory_transactions" (customer_id);

-- ============================================
-- UPGRADE QUERIES (Apply Changes)
-- ============================================

-- 1. Agency table enhancements (Tickets #12, #13)
ALTER TABLE "ASP_agencies" 
ADD COLUMN IF NOT EXISTS address1 VARCHAR(255),
ADD COLUMN IF NOT EXISTS address2 VARCHAR(255),
ADD COLUMN IF NOT EXISTS city VARCHAR(100),
ADD COLUMN IF NOT EXISTS state VARCHAR(100),
ADD COLUMN IF NOT EXISTS country VARCHAR(100) DEFAULT 'India',
ADD COLUMN IF NOT EXISTS registration_number VARCHAR(50);

-- Migrate existing address data to address1
UPDATE "ASP_agencies" 
SET address1 = address 
WHERE address IS NOT NULL AND address1 IS NULL;

-- 2. Customer table enhancements (Ticket #14)
ALTER TABLE "ASP_customers" 
ADD COLUMN IF NOT EXISTS customer_code VARCHAR(10) UNIQUE;

-- 3. Location table - unique constraint (Ticket #16)
ALTER TABLE "ASP_locations" 
ADD CONSTRAINT uq_location_name_agency UNIQUE (name, agency_id);

-- 4. Order table enhancements for POS (Tickets #20, #23, #24)
ALTER TABLE "ASP_orders" 
ADD COLUMN IF NOT EXISTS payment_mode VARCHAR(20) DEFAULT 'cash',
ADD COLUMN IF NOT EXISTS order_type VARCHAR(20) DEFAULT 'local',
ADD COLUMN IF NOT EXISTS discount_percentage NUMERIC(5, 2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS handling_charges NUMERIC(10, 2) DEFAULT 0;

-- 5. Product table enhancements (Ticket #18)
ALTER TABLE "ASP_products" 
ADD COLUMN IF NOT EXISTS hsn_code VARCHAR(20),
ADD COLUMN IF NOT EXISTS item_code VARCHAR(50);


-- ============================================
-- DOWNGRADE QUERIES (Revert Changes)
-- ============================================

-- Remove Agency fields
ALTER TABLE "ASP_agencies" 
DROP COLUMN IF EXISTS address1,
DROP COLUMN IF EXISTS address2,
DROP COLUMN IF EXISTS city,
DROP COLUMN IF EXISTS state,
DROP COLUMN IF EXISTS country,
DROP COLUMN IF EXISTS registration_number;

-- Remove Customer fields
ALTER TABLE "ASP_customers" 
DROP COLUMN IF EXISTS customer_code;

-- Remove Location constraint
ALTER TABLE "ASP_locations" 
DROP CONSTRAINT IF EXISTS uq_location_name_agency;

-- Remove Order fields
ALTER TABLE "ASP_orders" 
DROP COLUMN IF EXISTS payment_mode,
DROP COLUMN IF EXISTS order_type,
DROP COLUMN IF EXISTS discount_percentage,
DROP COLUMN IF EXISTS handling_charges;

-- Remove Product fields
ALTER TABLE "ASP_products" 
DROP COLUMN IF EXISTS hsn_code,
DROP COLUMN IF EXISTS item_code;


-- Add service_technician_id column to ASP_users table
ALTER TABLE "ASP_users" ADD COLUMN IF NOT EXISTS "service_technician_id" VARCHAR(50) UNIQUE;
CREATE INDEX IF NOT EXISTS "idx_users_service_technician_id" ON "ASP_users" ("service_technician_id");

-- Add agency_type column to ASP_agencies table
ALTER TABLE public."ASP_agencies" 
ADD COLUMN IF NOT EXISTS agency_type VARCHAR(50) NOT NULL DEFAULT 'sales';

-- Create an index on the new column
CREATE INDEX IF NOT EXISTS idx_agency_type ON public."ASP_agencies" (agency_type);

-- Backfill existing agencies with the default value
UPDATE public."ASP_agencies" SET agency_type = 'sales' WHERE agency_type IS NULL;


-- Add the work_order_line_item_id column to the inventory transactions table
ALTER TABLE "ASP_inventory_transactions" ADD COLUMN work_order_line_item_id INTEGER;

-- Add a foreign key constraint to link work_order_line_item_id to the work order line items table
ALTER TABLE "ASP_inventory_transactions" ADD CONSTRAINT fk_inventory_transactions_work_order_line_item_id 
FOREIGN KEY (work_order_line_item_id) REFERENCES "ASP_work_order_line_items" (id);

-- Create an index on the new column for faster lookups
CREATE INDEX ix_ASP_inventory_transactions_work_order_line_item_id ON "ASP_inventory_transactions" (work_order_line_item_id);

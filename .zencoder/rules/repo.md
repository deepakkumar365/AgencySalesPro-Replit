# Repository Guide: AgencySales Pro

## Overview
- **Framework**: Flask (Blueprint-based modular app)
- **ORM**: SQLAlchemy via Flask-SQLAlchemy
- **Auth**: Web sessions + JWT for API
- **DB**: SQLite by default; PostgreSQL via DATABASE_URL
- **Entry**: `app.py` (creates and configures Flask app)
- **Main URL Prefixes**:
  - **Auth**: `/auth`
  - **Agency**: `/agency`
  - **Salesperson**: `/salesperson`
  - **Location**: `/location`
  - **Customer**: `/customer`
  - **Product**: `/product`
  - **Order**: `/order`
  - **POS**: `/pos`
  - **Billing**: `/billing`
  - **Inventory**: `/inventory`
  - **Reports**: `/reports`
  - **Masters**: `/masters`
  - **Public API**: `/api/v1`

## Run & Environment
- **Run local**: `python app.py` or via your WSGI runner.
- **ENV vars**:
  - **SESSION_SECRET**: Flask secret key (default: `dev-secret-key`)
  - **DATABASE_URL**: e.g. `sqlite:///agency_sales.db` or Postgres; `postgres://` is normalized to `postgresql://`
  - **JWT_SECRET_KEY**: JWT secret
  - **DEFAULT_ADMIN_USER / DEFAULT_ADMIN_EMAIL / DEFAULT_ADMIN_PASS**: Seed super admin on first run

## Data Model Highlights (models.py)
- **Agency**: `ASP_agencies`
- **User**: `ASP_users` (roles: `super_admin`, `agency_admin`, `staff`, `salesperson`, `pos_user`)
- **Location**: `ASP_locations` (FK agency)
- **Customer**: `ASP_customers` (FK location)
- **Product**: `ASP_products` (global master)
- **ProductAgency**: `ASP_product_agencies` (per-agency overrides, unique `(product_id, agency_id)`)
- **Order / OrderItem**: `ASP_orders`, `ASP_order_items`
- **Billing**: `ASP_invoices`, `ASP_payments`, etc.

## Key Conventions
- **Global Product Master** with optional per-agency overrides in `ProductAgency`.
- **Mapping uniqueness**: enforced by DB UniqueConstraint `uq_product_agency`.
- **Legacy compatibility**: Product has legacy fields synced from new master fields when needed.

## Recent Behavioral Notes
- **Order create**: When non-super-admin adds a product not yet mapped to their agency, a `ProductAgency` mapping is auto-created (or reactivated) to avoid SKU selection failures.
- **Product create**: If SKU exists, system maps existing product to chosen/current agency (if provided) instead of creating duplicate; respects unique `(product_id, agency_id)`.

## Blueprints
- `auth`, `agency`, `salesperson`, `location`, `customer`, `product`, `order`, `pos`, `billing`, `inventory`, `reports`, `masters`, `product_overrides`, `api`.

## Templates & Frontend
- Jinja2 templates in `/templates` with Bootstrap 5.
- Order form uses Tom Select for searching customers and products; product autocomplete endpoint: `/order/api/search-products`.

## Import/Export
- Utilities in `utils/excel_utils.py` for product/order Excel import/export.

## Deployment
- `render.yaml` and `gunicorn.conf.py` present; `startup.sh` for startup tasks.

## Useful Paths
- `instance/agency_sales.db` (default SQLite)
- `migrations/` for SQL migrations

## Support
This file was auto-generated to speed up code navigation and maintenance. Update as needed when routes or behaviors change.
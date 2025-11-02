from extensions import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# Installation / App Settings
class AppSetting(db.Model):
    __tablename__ = 'ASP_settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.String(255), nullable=False)

    @staticmethod
    def get(key, default=None):
        rec = AppSetting.query.filter_by(key=key).first()
        return rec.value if rec else default

    @staticmethod
    def set(key, value):
        rec = AppSetting.query.filter_by(key=key).first()
        if rec:
            rec.value = str(value)
        else:
            rec = AppSetting(key=key, value=str(value))
            db.session.add(rec)
        db.session.commit()

class Agency(db.Model):
    __tablename__ = 'ASP_agencies'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    
    # Address fields (Ticket #12)
    address = db.Column(db.Text)  # Kept for backward compatibility
    address1 = db.Column(db.String(255))
    address2 = db.Column(db.String(255))
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    country = db.Column(db.String(100), default='India')
    
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    registration_number = db.Column(db.String(50))  # Ticket #12
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    agency_manager_id = db.Column(db.Integer, db.ForeignKey('ASP_users.id'), nullable=True, index=True)
    
    # Relationships
    users = db.relationship('User', backref='agency', lazy=True, foreign_keys='User.agency_id')
    locations = db.relationship('Location', backref='agency', lazy=True)
    product_mappings = db.relationship('ProductAgency', backref='agency', lazy=True)
    customer_mappings = db.relationship('CustomerAgency', backref='agency', lazy=True)
    orders = db.relationship('Order', backref='agency', lazy=True)
    invoices = db.relationship('Invoice', backref='agency', lazy=True)
    suppliers = db.relationship('Supplier', backref='agency', lazy=True)
    manager = db.relationship('User', foreign_keys=[agency_manager_id])

class User(db.Model):
    __tablename__ = 'ASP_users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    # Role can be: super_admin, support, agency_manager, agency_admin, staff, salesperson, pos_user, accountant
    # - super_admin: Full Tenant/Agency/User Management (view-only), no Inventory/Sales/Reports/Forecasting
    # - support: Full access to all features (support team)
    # - agency_manager: Full control within managed agencies, View-only Tenant Management
    # - agency_admin: Full agency operations, Limited Agency/Payment Config management
    # - staff: Operational role - Full Inventory/Sales, View Forecasting, Limited Reports
    # - salesperson: Sales-focused - manage orders, view inventory
    # - pos_user: POS terminal user - access POS, billing, basic orders
    # - accountant: Finance role - View Inventory/Sales, Full Reports, View Payment Config
    role = db.Column(db.String(20), nullable=False)
    # New FK to normalized roles table (nullable for gradual migration)
    role_id = db.Column(db.Integer, db.ForeignKey('ASP_roles.id'), nullable=True, index=True)
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), index=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    orders = db.relationship('Order', backref='salesperson', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

# --- New RBAC models: Role, Permission, RolePermission, MenuItem ---
class Role(db.Model):
    __tablename__ = 'ASP_roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text)
    is_system = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    permissions = db.relationship('Permission', secondary='ASP_role_permissions',
                                  backref=db.backref('roles', lazy='dynamic'))

    def __repr__(self):
        return f"<Role {self.name}>"

class Permission(db.Model):
    __tablename__ = 'ASP_permissions'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    code = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Permission {self.code}>"

class RolePermission(db.Model):
    __tablename__ = 'ASP_role_permissions'
    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('ASP_roles.id', ondelete='CASCADE'), nullable=False)
    permission_id = db.Column(db.Integer, db.ForeignKey('ASP_permissions.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('role_id', 'permission_id', name='uq_role_permission'),
    )

class MenuItem(db.Model):
    __tablename__ = 'ASP_menu_items'
    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('ASP_menu_items.id', ondelete='CASCADE'))
    name = db.Column(db.String(100), nullable=False)
    display_name = db.Column(db.String(100))  # Optional display name for distinguishing menus with same name
    url = db.Column(db.String(255))
    icon = db.Column(db.String(50))
    order_index = db.Column(db.Integer, default=0)
    # Option: reference permission by code for easier matching in templates
    required_permission_code = db.Column(db.String(100), db.ForeignKey('ASP_permissions.code', ondelete='SET NULL'), nullable=True)
    dashboard_for_role = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)

    # Relationships
    children = db.relationship('MenuItem', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')
    role_mappings = db.relationship('MenuRole', backref='menu_item', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<MenuItem {self.name}>"

class MenuRole(db.Model):
    """Mapping table for Menu-Role many-to-many relationship"""
    __tablename__ = 'ASP_menu_roles'
    id = db.Column(db.Integer, primary_key=True)
    menu_id = db.Column(db.Integer, db.ForeignKey('ASP_menu_items.id', ondelete='CASCADE'), nullable=False, index=True)
    role_id = db.Column(db.Integer, db.ForeignKey('ASP_roles.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    role = db.relationship('Role', backref='menu_mappings')

    __table_args__ = (
        db.UniqueConstraint('menu_id', 'role_id', name='uq_menu_role'),
    )

    def __repr__(self):
        return f"<MenuRole menu={self.menu_id} role={self.role_id}>"

class Location(db.Model):
    __tablename__ = 'ASP_locations'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text)
    city = db.Column(db.String(50))
    state = db.Column(db.String(50))
    zip_code = db.Column(db.String(10))
    phone = db.Column(db.String(20))
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    customers = db.relationship('Customer', backref='location', lazy=True)
    
    # Ticket #16: Unique constraint on location name per agency
    __table_args__ = (
        db.UniqueConstraint('name', 'agency_id', name='uq_location_name_agency'),
    )

class CustomerAgency(db.Model):
    """Mapping table for Customer-Agency many-to-many relationship"""
    __tablename__ = 'ASP_customer_agencies'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('ASP_customers.id'), nullable=False, index=True)
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('customer_id', 'agency_id', name='uq_customer_agency'),
    )

class Customer(db.Model):
    __tablename__ = 'ASP_customers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    customer_code = db.Column(db.String(10), unique=True)  # Ticket #14: 6-digit alphanumeric code
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.Text)
    city = db.Column(db.String(50))  # For better search and display
    state = db.Column(db.String(50))  # For regional filtering
    pincode = db.Column(db.String(10))  # Indian postal code
    gst_number = db.Column(db.String(20))  # GST registration number
    credit_limit = db.Column(db.Numeric(10, 2), default=0)  # Credit limit
    credit_period = db.Column(db.Integer, default=30)  # Credit days
    location_id = db.Column(db.Integer, db.ForeignKey('ASP_locations.id'), nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    orders = db.relationship('Order', backref='customer', lazy=True)
    subscription = db.relationship('Subscription', back_populates='customer_rel', uselist=False)
    agency_mappings = db.relationship('CustomerAgency', backref='customer', lazy=True, cascade='all, delete-orphan')

class Product(db.Model):
    __tablename__ = 'ASP_products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    sku = db.Column(db.String(50), unique=True, nullable=False)
    
    # New master data fields (global defaults)
    buy_price = db.Column(db.Numeric(10, 2))  # Global cost/purchase price
    sell_price = db.Column(db.Numeric(10, 2))  # Default selling price
    mrp_price = db.Column(db.Numeric(10, 2))  # Maximum Retail Price
    margin = db.Column(db.Numeric(5, 2))  # Margin percentage
    
    # Ticket #18: Additional fields for bulk upload
    hsn_code = db.Column(db.String(20))  # HSN code for tax purposes
    item_code = db.Column(db.String(50))  # Item code
    
    # Foreign key relationships to master tables (global defaults)
    category_id = db.Column(db.Integer, db.ForeignKey('ASP_categories.id'), index=True)
    uom_id = db.Column(db.Integer, db.ForeignKey('ASP_uoms.id'), index=True)
    tax_master_id = db.Column(db.Integer, db.ForeignKey('ASP_tax_masters.id'), index=True)
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    order_items = db.relationship('OrderItem', backref='product', lazy=True)
    agency_mappings = db.relationship('ProductAgency', backref='product', lazy=True, cascade='all, delete-orphan')
    # Note: category_ref, uom_ref, and tax_master_ref are created via backref from the respective master tables
    
    @property
    def calculate_margin(self):
        """Calculate margin percentage based on buy and sell prices"""
        if self.buy_price and self.sell_price:
            return round(((self.sell_price - self.buy_price) / self.buy_price) * 100, 2)
        return 0
    
    def get_display_name_for_agency(self, agency_id):
        """
        Get the effective display name for this product in a specific agency.
        Respects agency-specific overrides from ProductAgency.
        
        Args:
            agency_id: The ID of the agency
            
        Returns:
            The agency-specific display name if it exists, otherwise the global product name
        """
        if agency_id:
            mapping = ProductAgency.query.filter_by(product_id=self.id, agency_id=agency_id).first()
            if mapping and mapping.display_name:
                return mapping.display_name
        return self.name
    
    # Backward compatibility methods
    def sync_legacy_fields(self):
        """Legacy columns removed; no-op to maintain compatibility with old calls."""
        return

class ProductAgency(db.Model):
    __tablename__ = 'ASP_product_agencies'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('ASP_products.id'), nullable=False, index=True)
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=False, index=True)
    
    # Per-agency overrides (optional; fall back to Product defaults)
    display_name = db.Column(db.String(150))
    buy_price = db.Column(db.Numeric(10, 2))   # New: agency-specific buy price
    sell_price = db.Column(db.Numeric(10, 2))  # Agency-specific sell price
    mrp_price = db.Column(db.Numeric(10, 2))   # New: agency-specific MRP
    category_id = db.Column(db.Integer, db.ForeignKey('ASP_categories.id'), index=True)
    uom_id = db.Column(db.Integer, db.ForeignKey('ASP_uoms.id'), index=True)
    tax_master_id = db.Column(db.Integer, db.ForeignKey('ASP_tax_masters.id'), index=True)
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships for convenience
    category_ref = db.relationship('Category', lazy=True)
    uom_ref = db.relationship('UOM', lazy=True)
    tax_master_ref = db.relationship('TaxMaster', lazy=True)
    
    __table_args__ = (
        db.UniqueConstraint('product_id', 'agency_id', name='uq_product_agency'),
    )

class Order(db.Model):
    __tablename__ = 'ASP_orders'
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('ASP_customers.id'), nullable=False, index=True)
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=False, index=True)
    salesperson_id = db.Column(db.Integer, db.ForeignKey('ASP_users.id'), nullable=False, index=True)
    status = db.Column(db.String(20), default='pending', index=True)  # pending, confirmed, shipped, delivered, cancelled
    payment_status = db.Column(db.String(20), default='pending')  # pending, partial, paid, overdue
    total_amount = db.Column(db.Numeric(10, 2), default=0)
    subtotal_amount = db.Column(db.Numeric(10, 2), default=0)  # Total before tax
    total_tax_amount = db.Column(db.Numeric(10, 2), default=0)  # Sum of all line taxes
    total_items_count = db.Column(db.Integer, default=0)  # Number of line items
    discount = db.Column(db.Numeric(10, 2), default=0)
    tax = db.Column(db.Numeric(10, 2), default=0)
    notes = db.Column(db.Text)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    delivery_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Ticket #20, #23, #24: POS-specific fields
    payment_mode = db.Column(db.String(20))  # cash, credit, credit_sale
    order_type = db.Column(db.String(20))  # local, others
    discount_percentage = db.Column(db.Numeric(5, 2), default=0)  # Discount percentage for entire order
    handling_charges = db.Column(db.Numeric(10, 2), default=0)  # Additional handling charges
    
    # Relationships
    order_items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')

class OrderItem(db.Model):
    __tablename__ = 'ASP_order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('ASP_orders.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('ASP_products.id'), nullable=False, index=True)
    quantity = db.Column(db.Numeric(10, 3), nullable=False)  # Changed from Integer to Numeric to support decimal values (e.g., 1.25, 0.75)
    uom = db.Column(db.String(20), default='pcs')  # Unit of Measure: pcs, kg, ltr, etc.
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)  # Original selling price
    mrp_price = db.Column(db.Numeric(10, 2), nullable=False)  # Maximum Retail Price
    discount_percentage = db.Column(db.Numeric(5, 2), default=0)  # Discount percentage
    discounted_price = db.Column(db.Numeric(10, 2), nullable=False)  # Price after discount
    tax_code = db.Column(db.String(20), default='GST18')  # Indian tax code
    tax_rate = db.Column(db.Numeric(5, 2), default=18.00)  # Tax percentage
    tax_amount = db.Column(db.Numeric(10, 2), default=0)  # Calculated tax amount
    line_total = db.Column(db.Numeric(10, 2), nullable=False)  # Final line amount with tax
    total_price = db.Column(db.Numeric(10, 2), nullable=False)  # For backward compatibility
    product_name = db.Column(db.String(150))  # Effective product name at order creation (respects agency-specific overrides)
    
    def calculate_totals(self):
        """Calculate item totals after setting all values"""
        if self.quantity and self.unit_price:
            # Calculate discounted price
            discount_amount = (self.unit_price * self.discount_percentage / 100) if self.discount_percentage else 0
            self.discounted_price = self.unit_price - discount_amount
            # Calculate tax amount
            self.tax_amount = (self.discounted_price * self.quantity * self.tax_rate / 100) if self.tax_rate else 0
            # Calculate line total
            self.line_total = (self.discounted_price * self.quantity) + self.tax_amount
            # For backward compatibility
            self.total_price = self.line_total

class DeliveryChallan(db.Model):
    """Delivery Challan for tracking shipments"""
    __tablename__ = 'ASP_delivery_challans'
    id = db.Column(db.Integer, primary_key=True)
    challan_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey('ASP_orders.id'), nullable=False, index=True)
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('ASP_customers.id'), nullable=False, index=True)
    
    # Delivery details
    delivery_date = db.Column(db.DateTime)
    delivery_address = db.Column(db.Text)
    transporter_name = db.Column(db.String(100))
    vehicle_number = db.Column(db.String(50))
    lr_number = db.Column(db.String(50))  # Lorry Receipt Number
    e_way_bill_number = db.Column(db.String(50))
    
    # Status
    status = db.Column(db.String(20), default='pending', index=True)  # pending, in_transit, delivered, cancelled
    
    # Additional info
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('ASP_users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    order = db.relationship('Order', backref='delivery_challans', lazy=True)
    agency = db.relationship('Agency', backref='delivery_challans', lazy=True)
    customer = db.relationship('Customer', backref='delivery_challans', lazy=True)
    creator = db.relationship('User', backref='created_challans', lazy=True)
    items = db.relationship('DeliveryChallanItem', backref='challan', lazy=True, cascade='all, delete-orphan')

class DeliveryChallanItem(db.Model):
    """Line items for delivery challans with product name snapshot"""
    __tablename__ = 'ASP_delivery_challan_items'
    id = db.Column(db.Integer, primary_key=True)
    challan_id = db.Column(db.Integer, db.ForeignKey('ASP_delivery_challans.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('ASP_products.id'), nullable=False, index=True)
    quantity = db.Column(db.Numeric(10, 3), nullable=False)
    uom = db.Column(db.String(20), default='pcs')  # Unit of Measure: pcs, kg, ltr, etc.
    product_name = db.Column(db.String(150))  # Effective product name at creation (respects agency-specific overrides)
    
    # Relationships
    product = db.relationship('Product', backref='delivery_challan_items', lazy=True)

class ActivityLog(db.Model):
    __tablename__ = 'ASP_activity_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('ASP_users.id'), nullable=False, index=True)
    action = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='activity_logs', lazy=True)

# Billing Module Models
class Invoice(db.Model):
    __tablename__ = 'ASP_invoices'
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey('ASP_orders.id'), nullable=False, index=True)
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('ASP_customers.id'), nullable=False, index=True)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    tax_amount = db.Column(db.Numeric(10, 2), default=0)
    discount_amount = db.Column(db.Numeric(10, 2), default=0)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(20), default='pending', index=True)  # pending, paid, overdue, cancelled
    issue_date = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime)
    payment_terms = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    order = db.relationship('Order', backref='invoice', lazy=True)
    customer = db.relationship('Customer', backref='invoices', lazy=True)
    payments = db.relationship('Payment', backref='invoice', lazy=True)
    items = db.relationship('InvoiceItem', backref='invoice', lazy=True, cascade='all, delete-orphan')

class InvoiceItem(db.Model):
    """Line items for invoices with product name snapshot"""
    __tablename__ = 'ASP_invoice_items'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('ASP_invoices.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('ASP_products.id'), nullable=False, index=True)
    quantity = db.Column(db.Numeric(10, 3), nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    tax_amount = db.Column(db.Numeric(10, 2), default=0)
    total_price = db.Column(db.Numeric(10, 2), nullable=False)
    product_name = db.Column(db.String(150))  # Effective product name at creation (respects agency-specific overrides)
    
    # Relationships
    product = db.relationship('Product', backref='invoice_items', lazy=True)

class Payment(db.Model):
    __tablename__ = 'ASP_payments'
    id = db.Column(db.Integer, primary_key=True)
    payment_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('ASP_invoices.id'), nullable=False, index=True)
    payment_method_id = db.Column(db.Integer, db.ForeignKey('ASP_payment_methods.id'), nullable=False, index=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    transaction_id = db.Column(db.String(100))  # External payment gateway transaction ID
    status = db.Column(db.String(20), default='completed')  # completed, pending, failed, refunded
    notes = db.Column(db.Text)
    processed_by = db.Column(db.Integer, db.ForeignKey('ASP_users.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    payment_method = db.relationship('PaymentMethod', backref='payments', lazy=True)
    processor = db.relationship('User', backref='processed_payments', lazy=True)

class PaymentMethod(db.Model):
    __tablename__ = 'ASP_payment_methods'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # Cash, Credit Card, Debit Card, Digital Wallet, etc.
    code = db.Column(db.String(50), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    agency_ref = db.relationship('Agency', backref='payment_methods', lazy=True)

class TaxRule(db.Model):
    __tablename__ = 'ASP_tax_rules'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    rate = db.Column(db.Numeric(5, 4), nullable=False)  # Tax rate as decimal (e.g., 0.0825 for 8.25%)
    location_id = db.Column(db.Integer, db.ForeignKey('ASP_locations.id'), nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    location = db.relationship('Location', backref='tax_rules', lazy=True)

class IndianTaxCode(db.Model):
    __tablename__ = 'ASP_indian_tax_codes'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)  # GST0, GST5, GST12, GST18, GST28
    name = db.Column(db.String(100), nullable=False)  # Goods and Services Tax 18%
    rate = db.Column(db.Numeric(5, 2), nullable=False)  # 18.00 (percentage)
    description = db.Column(db.Text)  # Description of what items this applies to
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Inventory Module Models
class Supplier(db.Model):
    __tablename__ = 'ASP_suppliers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact_person = db.Column(db.String(100))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    notes = db.Column(db.Text) 
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    purchase_orders = db.relationship('PurchaseOrder', backref='supplier', lazy=True)

class PurchaseOrder(db.Model):
    __tablename__ = 'ASP_purchase_orders'
    id = db.Column(db.Integer, primary_key=True)
    po_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('ASP_suppliers.id'), nullable=False, index=True)
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=False, index=True)
    total_amount = db.Column(db.Numeric(10, 2), default=0)
    status = db.Column(db.String(20), default='pending', index=True)  # pending, sent, received, cancelled
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    expected_delivery = db.Column(db.DateTime)
    received_date = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('ASP_users.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    agency_ref = db.relationship('Agency', backref='purchase_orders', lazy=True)
    creator = db.relationship('User', backref='created_purchase_orders', lazy=True)
    po_items = db.relationship('PurchaseOrderItem', backref='purchase_order', lazy=True, cascade='all, delete-orphan')

class PurchaseOrderItem(db.Model):
    __tablename__ = 'ASP_purchase_order_items'
    id = db.Column(db.Integer, primary_key=True)
    po_id = db.Column(db.Integer, db.ForeignKey('ASP_purchase_orders.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('ASP_products.id'), nullable=False, index=True)
    quantity_ordered = db.Column(db.Numeric(10, 2), nullable=False)  # Changed from Integer to Numeric to support decimal values
    quantity_received = db.Column(db.Numeric(10, 2), default=0)  # Changed from Integer to Numeric to support decimal values
    unit_cost = db.Column(db.Numeric(10, 2), nullable=False)
    total_cost = db.Column(db.Numeric(10, 2), nullable=False)
    product_name = db.Column(db.String(150))  # Effective product name at creation (respects agency-specific overrides)
    
    # Relationships
    product = db.relationship('Product', backref='po_items', lazy=True)

class InventoryTransaction(db.Model):
    __tablename__ = 'ASP_inventory_transactions'
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=True, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('ASP_customers.id'), nullable=True, index=True)
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('ASP_products.id'), nullable=False, index=True)
    transaction_type = db.Column(db.String(50), nullable=False, index=True)  # e.g., 'purchase', 'sale', 'adjustment', 'return'
    quantity_change = db.Column(db.Integer, nullable=False)  # Positive for increase, negative for decrease
    quantity_before = db.Column(db.Integer, nullable=False)
    quantity_after = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Numeric(10, 2))
    reference_id = db.Column(db.String(50), index=True)  # Order ID, PO ID, or other reference
    reference_type = db.Column(db.String(50), index=True)  # e.g., 'order', 'purchase_order', 'manual_adjustment'
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('ASP_users.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    product = db.relationship('Product', backref='inventory_transactions')
    user = db.relationship('User', backref='inventory_transactions', foreign_keys=[created_by])
    agency = db.relationship('Agency', backref='inventory_transactions')
    customer = db.relationship('Customer', backref='inventory_transactions')

    # By removing the custom __init__, we allow SQLAlchemy's default
    # constructor to handle all model attributes, including the newly
    # added agency_id and customer_id. This is the key fix.
    # No __init__ method should be here.

    __table_args__ = (
        db.CheckConstraint('agency_id IS NOT NULL OR customer_id IS NOT NULL', 
                           name='chk_inventory_transaction_has_context'),
    )

    @property
    def created_by_user(self):
        return self.user.full_name if self.user else 'System'

class StockAdjustment(db.Model):
    __tablename__ = 'ASP_stock_adjustments'
    id = db.Column(db.Integer, primary_key=True)
    adjustment_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=False, index=True)
    reason = db.Column(db.String(100), nullable=False)  # damage, theft, count_correction, etc.
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('ASP_users.id'), nullable=False, index=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('ASP_users.id'), index=True)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime)
    
    # Relationships
    agency_ref = db.relationship('Agency', backref='stock_adjustments', lazy=True)
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_adjustments', lazy=True)
    approver = db.relationship('User', foreign_keys=[approved_by], backref='approved_adjustments', lazy=True)
    adjustment_items = db.relationship('StockAdjustmentItem', backref='adjustment', lazy=True, cascade='all, delete-orphan')

class StockAdjustmentItem(db.Model):
    __tablename__ = 'ASP_stock_adjustment_items'
    id = db.Column(db.Integer, primary_key=True)
    adjustment_id = db.Column(db.Integer, db.ForeignKey('ASP_stock_adjustments.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('ASP_products.id'), nullable=False, index=True)
    quantity_before = db.Column(db.Integer, nullable=False)
    quantity_change = db.Column(db.Integer, nullable=False)  # Can be positive or negative
    quantity_after = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(200))
    
    # Relationships
    product = db.relationship('Product', backref='adjustment_items', lazy=True)

class LowStockAlert(db.Model):
    __tablename__ = 'ASP_low_stock_alerts'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('ASP_products.id'), nullable=False, index=True)
    threshold_quantity = db.Column(db.Integer, nullable=False)
    current_quantity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='active', index=True)  # active, resolved, ignored
    alerted_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
    resolved_by = db.Column(db.Integer, db.ForeignKey('ASP_users.id'), index=True)
    
    # Relationships
    product = db.relationship('Product', backref='stock_alerts', lazy=True)
    resolver = db.relationship('User', backref='resolved_alerts', lazy=True)

# Master Data Models
class Category(db.Model):
    __tablename__ = 'ASP_categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    short_name = db.Column(db.String(3))  # 3-letter short code (validated in app)
    description = db.Column(db.Text)
    # agency_id removed: global master
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    products = db.relationship('Product', backref='category_ref', lazy=True)

class UOM(db.Model):
    __tablename__ = 'ASP_uoms'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    short_name = db.Column(db.String(10), nullable=False)
    description = db.Column(db.Text)
    # agency_id removed: global master
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    products = db.relationship('Product', backref='uom_ref', lazy=True)

class TaxMaster(db.Model):
    __tablename__ = 'ASP_tax_masters'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    tax_code = db.Column(db.String(20), nullable=False, unique=True)
    tax_rate = db.Column(db.Numeric(5, 2), nullable=False)
    description = db.Column(db.Text)
    # agency_id removed: global master
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    products = db.relationship('Product', backref='tax_master_ref', lazy=True)

# Subscription Module Models
class SubscriptionPlan(db.Model):
    __tablename__ = 'ASP_subscription_plans'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    code = db.Column(db.String(50), nullable=False, unique=True)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    billing_cycle = db.Column(db.String(20), nullable=False, default='monthly')  # monthly, quarterly, half_yearly, yearly
    features = db.Column(db.Text)  # JSON string or comma-separated features
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    subscriptions = db.relationship('Subscription', backref='plan', lazy=True)
    subscription_items = db.relationship('SubscriptionItem', backref='plan', lazy=True)

class Subscription(db.Model):
    __tablename__ = 'ASP_subscriptions'
    id = db.Column(db.Integer, primary_key=True)
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=True, unique=True, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('ASP_customers.id'), nullable=True, unique=True, index=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('ASP_subscription_plans.id'), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default='active', index=True)  # active, suspended, cancelled, expired
    start_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    end_date = db.Column(db.DateTime)
    trial_end_date = db.Column(db.DateTime)  # For future use
    next_billing_date = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    agency_rel = db.relationship('Agency', backref='subscription', lazy=True, uselist=False)
    customer_rel = db.relationship('Customer', back_populates='subscription', lazy=True, uselist=False)
    invoices = db.relationship('SubscriptionInvoice', backref='subscription', lazy=True, cascade='all, delete-orphan')
    items = db.relationship('SubscriptionItem', backref='subscription', lazy=True, cascade='all, delete-orphan')
    
    __table_args__ = (
        db.CheckConstraint('num_nonnulls(agency_id, customer_id) = 1', name='chk_subscription_owner'),
        # num_nonnulls is a postgres function. For other DBs, this might be:
        # db.CheckConstraint('(agency_id IS NOT NULL AND customer_id IS NULL) OR (agency_id IS NULL AND customer_id IS NOT NULL)', name='chk_subscription_owner'),
    )
    @property
    def owner(self):
        """Returns the owner (Agency or Customer) of the subscription."""
        if self.agency_rel:
            return self.agency_rel
        elif self.customer_rel:
            return self.customer_rel
        return None

    @property
    def is_active(self):
        """Check if subscription is currently active"""
        return self.status == 'active'
    
    @property
    def is_expired(self):
        """Check if subscription has expired"""
        if self.end_date and self.end_date < datetime.utcnow():
            return True
        return False
    
    @property
    def days_until_renewal(self):
        """Calculate days until next billing"""
        if self.next_billing_date:
            delta = self.next_billing_date - datetime.utcnow()
            return delta.days
        return None

class SubscriptionInvoice(db.Model):
    __tablename__ = 'ASP_subscription_invoices'
    id = db.Column(db.Integer, primary_key=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey('ASP_subscriptions.id'), nullable=False, index=True)
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=True, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('ASP_customers.id'), nullable=True, index=True)
    invoice_number = db.Column(db.String(50), nullable=False, unique=True, index=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='draft', index=True)  # draft, issued, paid, overdue, cancelled
    issue_date = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, nullable=False)
    paid_at = db.Column(db.DateTime)
    billing_period_start = db.Column(db.DateTime, nullable=False)
    billing_period_end = db.Column(db.DateTime, nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    agency_rel = db.relationship('Agency', backref='subscription_invoices', lazy=True)
    customer_rel = db.relationship('Customer', backref='subscription_invoices', lazy=True)
    
    @property
    def is_overdue(self):
        """Check if invoice is overdue"""
        if self.status in ['issued', 'draft'] and self.due_date < datetime.utcnow():
            return True
        return False
    
    @property
    def days_overdue(self):
        """Calculate days overdue"""
        if self.is_overdue:
            delta = datetime.utcnow() - self.due_date
            return delta.days
        return 0

class SubscriptionItem(db.Model):
    __tablename__ = 'ASP_subscription_items'
    id = db.Column(db.Integer, primary_key=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey('ASP_subscriptions.id'), nullable=False, index=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('ASP_subscription_plans.id'), nullable=False, index=True)
    item_description = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @property
    def total_price(self):
        """Calculate total price for this item"""
        return self.quantity * self.unit_price

# Job Accounting Module Models
class Job(db.Model):
    __tablename__ = 'ASP_jobs'
    id = db.Column(db.Integer, primary_key=True)
    job_number = db.Column(db.String(50), unique=True, nullable=False, index=True) # Renamed from job_name to name
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    job_type = db.Column(db.String(50), default='client_project')  # client_project, internal_project, service
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('ASP_customers.id'), index=True)  # Optional for internal projects
    order_id = db.Column(db.Integer, db.ForeignKey('ASP_orders.id'), index=True)  # Link to order if auto-created
    assigned_to = db.Column(db.Integer, db.ForeignKey('ASP_users.id'), index=True)  # Project manager/owner
    status = db.Column(db.String(20), default='draft', index=True)  # draft, planning, active, on_hold, review, completed, cancelled
    
    # Financial tracking
    budget_amount = db.Column(db.Numeric(12, 2), default=0)
    estimated_cost = db.Column(db.Numeric(12, 2), default=0)
    
    # Dates
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    completed_date = db.Column(db.DateTime)
    
    # Metadata
    created_by = db.Column(db.Integer, db.ForeignKey('ASP_users.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    agency_ref = db.relationship('Agency', backref='jobs', lazy=True)
    customer_ref = db.relationship('Customer', backref='jobs', lazy=True)
    order_ref = db.relationship('Order', backref='job', uselist=False, lazy=True)
    assigned_user = db.relationship('User', foreign_keys=[assigned_to], backref='assigned_jobs', lazy=True)
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_jobs', lazy=True)
    income_entries = db.relationship('JobIncome', backref='job', lazy=True, cascade='all, delete-orphan')
    expense_entries = db.relationship('JobExpense', backref='job', lazy=True, cascade='all, delete-orphan')
    
    @property
    def total_income(self):
        """Calculate total income for this job"""
        return sum(income.amount for income in self.income_entries if income.status == 'confirmed')
    
    @property
    def total_expenses(self):
        """Calculate total expenses for this job"""
        return sum(expense.amount for expense in self.expense_entries if expense.status == 'confirmed')
    
    @property
    def net_profit(self):
        """Calculate net profit (income - expenses)"""
        return self.total_income - self.total_expenses
    
    @property
    def profit_margin(self):
        """Calculate profit margin percentage"""
        if self.total_income > 0:
            return round((self.net_profit / self.total_income) * 100, 2)
        return 0
    
    @property
    def budget_variance(self):
        """Calculate variance from budget"""
        if self.budget_amount:
            return self.budget_amount - self.total_expenses
        return 0

class JobIncome(db.Model):
    __tablename__ = 'ASP_job_income'
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('ASP_jobs.id'), nullable=False, index=True)
    
    # Income details
    income_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    category = db.Column(db.String(50), nullable=False)  # deposit, payment, bonus, milestone, other
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    
    # Link to existing records (optional)
    order_id = db.Column(db.Integer, db.ForeignKey('ASP_orders.id'), index=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('ASP_invoices.id'), index=True)
    
    # Status and metadata
    status = db.Column(db.String(20), default='confirmed')  # pending, confirmed, cancelled
    payment_method = db.Column(db.String(50))  # cash, bank_transfer, check, card, etc.
    reference_number = db.Column(db.String(100))  # Transaction/check/reference number
    notes = db.Column(db.Text)
    
    created_by = db.Column(db.Integer, db.ForeignKey('ASP_users.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    order_ref = db.relationship('Order', backref='job_income_entries', lazy=True)
    invoice_ref = db.relationship('Invoice', backref='job_income_entries', lazy=True)
    creator = db.relationship('User', backref='created_job_income', lazy=True)

class JobExpense(db.Model):
    __tablename__ = 'ASP_job_expenses'
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('ASP_jobs.id'), nullable=False, index=True)
    
    # Expense details
    expense_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    category = db.Column(db.String(50), nullable=False)  # materials, labor, overhead, equipment, travel, other
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    
    # Link to existing records (optional)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey('ASP_purchase_orders.id'), index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('ASP_suppliers.id'), index=True)
    
    # Status and metadata
    status = db.Column(db.String(20), default='confirmed')  # pending, confirmed, cancelled
    payment_method = db.Column(db.String(50))  # cash, bank_transfer, check, card, etc.
    receipt_number = db.Column(db.String(100))  # Receipt/invoice number
    is_billable = db.Column(db.Boolean, default=True)  # Can this be billed to client?
    notes = db.Column(db.Text)
    
    created_by = db.Column(db.Integer, db.ForeignKey('ASP_users.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    purchase_order_ref = db.relationship('PurchaseOrder', backref='job_expense_entries', lazy=True)
    supplier_ref = db.relationship('Supplier', backref='job_expense_entries', lazy=True)
    creator = db.relationship('User', backref='created_job_expenses', lazy=True)

# Finance Module Models
class FinancePayment(db.Model):
    __tablename__ = 'ASP_finance_payments'
    id = db.Column(db.Integer, primary_key=True)
    payment_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=False, index=True)
    
    # Payment details
    payment_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    payee_type = db.Column(db.String(20), nullable=False)  # supplier, vendor, employee, other
    payee_id = db.Column(db.Integer, index=True)  # Reference to supplier_id or other entity
    payee_name = db.Column(db.String(200), nullable=False)  # Name of payee
    
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    mode_of_payment = db.Column(db.String(50), nullable=False)  # cash, bank_transfer, check, card, upi, etc.
    account_type = db.Column(db.String(20), default='cash')  # cash, bank
    
    # Optional fields
    reference_number = db.Column(db.String(100))  # Transaction/check/reference number
    notes = db.Column(db.Text)
    
    # Status
    status = db.Column(db.String(20), default='confirmed', index=True)  # pending, confirmed, cancelled
    
    # Metadata
    created_by = db.Column(db.Integer, db.ForeignKey('ASP_users.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    agency_ref = db.relationship('Agency', backref='finance_payments', lazy=True)
    creator = db.relationship('User', backref='created_finance_payments', lazy=True)
    purchase_orders = db.relationship('PaymentPurchaseOrder', backref='finance_payment', lazy=True, cascade='all, delete-orphan')
    
    @property
    def total_po_amount(self):
        """Calculate total amount from linked purchase orders"""
        return sum(po.amount for po in self.purchase_orders)

class PaymentPurchaseOrder(db.Model):
    """Link table between FinancePayment and Purchase Orders"""
    __tablename__ = 'ASP_finance_payment_purchase_orders'
    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('ASP_finance_payments.id'), nullable=False, index=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey('ASP_purchase_orders.id'), nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)  # Amount allocated to this PO
    notes = db.Column(db.Text)
    
    # Relationships
    purchase_order_ref = db.relationship('PurchaseOrder', backref='finance_payment_links', lazy=True)

class Receipt(db.Model):
    __tablename__ = 'ASP_receipts'
    id = db.Column(db.Integer, primary_key=True)
    receipt_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=False, index=True)
    
    # Receipt details
    receipt_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('ASP_customers.id'), index=True)  # Optional
    customer_name = db.Column(db.String(200), nullable=False)  # Name of customer/payer
    
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    mode_of_receipt = db.Column(db.String(50), nullable=False)  # cash, bank_transfer, check, card, upi, etc.
    account_type = db.Column(db.String(20), default='cash')  # cash, bank
    
    # Optional fields
    reference_number = db.Column(db.String(100))  # Transaction/check/reference number
    notes = db.Column(db.Text)
    
    # Status
    status = db.Column(db.String(20), default='confirmed', index=True)  # pending, confirmed, cancelled
    
    # Metadata
    created_by = db.Column(db.Integer, db.ForeignKey('ASP_users.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    agency_ref = db.relationship('Agency', backref='receipts', lazy=True)
    customer_ref = db.relationship('Customer', backref='receipts', lazy=True)
    creator = db.relationship('User', backref='created_receipts', lazy=True)
    sales_orders = db.relationship('ReceiptSalesOrder', backref='receipt', lazy=True, cascade='all, delete-orphan')
    
    @property
    def total_so_amount(self):
        """Calculate total amount from linked sales orders"""
        return sum(so.amount for so in self.sales_orders)

class ReceiptSalesOrder(db.Model):
    """Link table between Receipt and Sales Orders (Orders)"""
    __tablename__ = 'ASP_receipt_sales_orders'
    id = db.Column(db.Integer, primary_key=True)
    receipt_id = db.Column(db.Integer, db.ForeignKey('ASP_receipts.id'), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey('ASP_orders.id'), nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)  # Amount allocated to this order
    notes = db.Column(db.Text)
    
    # Relationships
    order_ref = db.relationship('Order', backref='receipt_links', lazy=True)

class PaymentConfiguration(db.Model):
    __tablename__ = 'ASP_payment_configurations'
    id = db.Column(db.Integer, primary_key=True)
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=False, unique=True)
    billing_type = db.Column(db.String(50), nullable=False)  # 'fixed' or 'variable'

    # Fields for 'fixed' type
    fixed_period = db.Column(db.String(50))  # 'monthly', 'quarterly', 'half_yearly', 'yearly'
    fixed_value = db.Column(db.Numeric(10, 2))
    currency_code = db.Column(db.String(10))

    # Fields for 'variable' type
    variable_type = db.Column(db.String(50))  # 'user_based', 'order_based', 'invoice_value_percentage'

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    agency = db.relationship('Agency', backref=db.backref('payment_configuration', uselist=False), lazy=True)

    def __repr__(self):
        return f'<PaymentConfiguration {self.id} for Agency {self.agency_id}>'

# Stock Forecasting & Profit Impact Analytics Models
class StockForecast(db.Model):
    """Stores weekly demand forecasts and shortage predictions"""
    __tablename__ = 'ASP_stock_forecasts'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('ASP_products.id'), nullable=False, index=True)
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=False, index=True)
    
    # Forecast period
    week_start_date = db.Column(db.Date, nullable=False, index=True)
    week_end_date = db.Column(db.Date, nullable=False)
    
    # Forecast data
    forecast_qty = db.Column(db.Numeric(10, 2), nullable=False)  # Predicted demand
    actual_stock = db.Column(db.Numeric(10, 2), nullable=False)  # Current available stock
    shortage_qty = db.Column(db.Numeric(10, 2), default=0)  # Shortage if forecast_qty > actual_stock
    excess_qty = db.Column(db.Numeric(10, 2), default=0)  # Excess if actual_stock > forecast_qty
    
    # Profit impact analysis
    profit_impact = db.Column(db.Numeric(12, 2), default=0)  # Estimated profit loss/gain
    holding_cost = db.Column(db.Numeric(10, 2), default=0)  # Cost of holding excess inventory
    opportunity_cost = db.Column(db.Numeric(10, 2), default=0)  # Lost sales due to shortage
    
    # Historical accuracy tracking
    actual_sales_qty = db.Column(db.Numeric(10, 2))  # Actual sales during the week (updated after week ends)
    forecast_accuracy = db.Column(db.Numeric(5, 2))  # Percentage accuracy (0-100)
    
    # Alert status
    alert_triggered = db.Column(db.Boolean, default=False)
    alert_sent_at = db.Column(db.DateTime)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    product = db.relationship('Product', backref='forecasts', lazy=True)
    agency = db.relationship('Agency', backref='forecasts', lazy=True)
    
    __table_args__ = (
        db.UniqueConstraint('product_id', 'agency_id', 'week_start_date', name='uq_forecast_product_agency_week'),
        db.Index('idx_forecast_week_agency', 'week_start_date', 'agency_id'),
    )

class ForecastAlertConfig(db.Model):
    """Configuration for forecast alert thresholds per agency"""
    __tablename__ = 'ASP_forecast_alert_configs'
    id = db.Column(db.Integer, primary_key=True)
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=False, index=True)
    
    # Alert thresholds
    shortage_threshold_qty = db.Column(db.Numeric(10, 2), default=10)  # Trigger alert if shortage > this
    shortage_threshold_percentage = db.Column(db.Numeric(5, 2), default=20)  # Or if shortage > X% of forecast
    excess_threshold_qty = db.Column(db.Numeric(10, 2), default=50)  # Trigger alert if excess > this
    excess_threshold_percentage = db.Column(db.Numeric(5, 2), default=30)  # Or if excess > X% of forecast
    
    # Category-specific thresholds (optional)
    category_id = db.Column(db.Integer, db.ForeignKey('ASP_categories.id'), index=True)
    
    # Alert delivery preferences
    email_alerts_enabled = db.Column(db.Boolean, default=True)
    dashboard_alerts_enabled = db.Column(db.Boolean, default=True)
    alert_recipients = db.Column(db.Text)  # Comma-separated email addresses
    
    # Metadata
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    agency = db.relationship('Agency', backref='forecast_alert_configs', lazy=True)
    category = db.relationship('Category', backref='forecast_alert_configs', lazy=True)
    
    __table_args__ = (
        db.UniqueConstraint('agency_id', 'category_id', name='uq_alert_config_agency_category'),
    )

class ForecastRefreshLog(db.Model):
    """Logs forecast refresh operations"""
    __tablename__ = 'ASP_forecast_refresh_logs'
    id = db.Column(db.Integer, primary_key=True)
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), index=True)
    
    # Refresh details
    refresh_type = db.Column(db.String(20), nullable=False)  # 'manual', 'scheduled'
    triggered_by = db.Column(db.Integer, db.ForeignKey('ASP_users.id'), index=True)
    
    # Results
    products_processed = db.Column(db.Integer, default=0)
    forecasts_created = db.Column(db.Integer, default=0)
    forecasts_updated = db.Column(db.Integer, default=0)
    alerts_triggered = db.Column(db.Integer, default=0)
    
    # Status
    status = db.Column(db.String(20), default='pending')  # pending, running, completed, failed
    error_message = db.Column(db.Text)
    
    # Timing
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    duration_seconds = db.Column(db.Integer)
    
    # Relationships
    agency = db.relationship('Agency', backref='forecast_refresh_logs', lazy=True)
    user = db.relationship('User', backref='forecast_refresh_logs', lazy=True)
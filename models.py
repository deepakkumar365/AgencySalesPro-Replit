from app import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class Agency(db.Model):
    __tablename__ = 'ASP_agencies'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    address = db.Column(db.Text)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    users = db.relationship('User', backref='agency', lazy=True)
    locations = db.relationship('Location', backref='agency', lazy=True)
    products = db.relationship('Product', backref='agency', lazy=True)
    orders = db.relationship('Order', backref='agency', lazy=True)
    invoices = db.relationship('Invoice', backref='agency', lazy=True)
    suppliers = db.relationship('Supplier', backref='agency', lazy=True)

class User(db.Model):
    __tablename__ = 'ASP_users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    role = db.Column(db.String(20), nullable=False)  # super_admin, agency_admin, staff, salesperson, pos_user
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'))
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

class Location(db.Model):
    __tablename__ = 'ASP_locations'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text)
    city = db.Column(db.String(50))
    state = db.Column(db.String(50))
    zip_code = db.Column(db.String(10))
    phone = db.Column(db.String(20))
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    customers = db.relationship('Customer', backref='location', lazy=True)

class Customer(db.Model):
    __tablename__ = 'ASP_customers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    city = db.Column(db.String(50))  # For better search and display
    state = db.Column(db.String(50))  # For regional filtering
    pincode = db.Column(db.String(10))  # Indian postal code
    gst_number = db.Column(db.String(20))  # GST registration number
    credit_limit = db.Column(db.Numeric(10, 2), default=0)  # Credit limit
    credit_period = db.Column(db.Integer, default=30)  # Credit days
    location_id = db.Column(db.Integer, db.ForeignKey('ASP_locations.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    orders = db.relationship('Order', backref='customer', lazy=True)

class Product(db.Model):
    __tablename__ = 'ASP_products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    sku = db.Column(db.String(50), unique=True, nullable=False)
    buy_price = db.Column(db.Numeric(10, 2), nullable=False)  # Cost/Purchase price
    sell_price = db.Column(db.Numeric(10, 2), nullable=False)  # Selling price
    mrp_price = db.Column(db.Numeric(10, 2), nullable=False)  # Maximum Retail Price
    margin = db.Column(db.Numeric(5, 2))  # Margin percentage
    
    # Foreign key relationships to master tables
    category_id = db.Column(db.Integer, db.ForeignKey('ASP_categories.id'))
    uom_id = db.Column(db.Integer, db.ForeignKey('ASP_uoms.id'))
    tax_master_id = db.Column(db.Integer, db.ForeignKey('ASP_tax_masters.id'))
    
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    order_items = db.relationship('OrderItem', backref='product', lazy=True)
    
    @property
    def calculate_margin(self):
        """Calculate margin percentage based on buy and sell prices"""
        if self.buy_price and self.sell_price:
            return round(((self.sell_price - self.buy_price) / self.buy_price) * 100, 2)
        return 0
    
    # Backward compatibility properties
    @property
    def price(self):
        """Backward compatibility: maps to sell_price"""
        return self.sell_price
    
    @property
    def cost(self):
        """Backward compatibility: maps to buy_price"""
        return self.buy_price

class Order(db.Model):
    __tablename__ = 'ASP_orders'
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('ASP_customers.id'), nullable=False)
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=False)
    salesperson_id = db.Column(db.Integer, db.ForeignKey('ASP_users.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, shipped, delivered, cancelled
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
    
    # Relationships
    order_items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')

class OrderItem(db.Model):
    __tablename__ = 'ASP_order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('ASP_orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('ASP_products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
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

class ActivityLog(db.Model):
    __tablename__ = 'ASP_activity_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('ASP_users.id'), nullable=False)
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
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('ASP_orders.id'), nullable=False)
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('ASP_customers.id'), nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    tax_amount = db.Column(db.Numeric(10, 2), default=0)
    discount_amount = db.Column(db.Numeric(10, 2), default=0)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, paid, overdue, cancelled
    issue_date = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime)
    payment_terms = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    order = db.relationship('Order', backref='invoice', lazy=True)
    customer = db.relationship('Customer', backref='invoices', lazy=True)
    payments = db.relationship('Payment', backref='invoice', lazy=True)

class Payment(db.Model):
    __tablename__ = 'ASP_payments'
    id = db.Column(db.Integer, primary_key=True)
    payment_number = db.Column(db.String(50), unique=True, nullable=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey('ASP_invoices.id'), nullable=False)
    payment_method_id = db.Column(db.Integer, db.ForeignKey('ASP_payment_methods.id'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    transaction_id = db.Column(db.String(100))  # External payment gateway transaction ID
    status = db.Column(db.String(20), default='completed')  # completed, pending, failed, refunded
    notes = db.Column(db.Text)
    processed_by = db.Column(db.Integer, db.ForeignKey('ASP_users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    payment_method = db.relationship('PaymentMethod', backref='payments', lazy=True)
    processor = db.relationship('User', backref='processed_payments', lazy=True)

class PaymentMethod(db.Model):
    __tablename__ = 'ASP_payment_methods'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # Cash, Credit Card, Debit Card, Digital Wallet, etc.
    code = db.Column(db.String(20), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    agency_ref = db.relationship('Agency', backref='payment_methods', lazy=True)

class TaxRule(db.Model):
    __tablename__ = 'ASP_tax_rules'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    rate = db.Column(db.Numeric(5, 4), nullable=False)  # Tax rate as decimal (e.g., 0.0825 for 8.25%)
    location_id = db.Column(db.Integer, db.ForeignKey('ASP_locations.id'), nullable=False)
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
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    purchase_orders = db.relationship('PurchaseOrder', backref='supplier', lazy=True)

class PurchaseOrder(db.Model):
    __tablename__ = 'ASP_purchase_orders'
    id = db.Column(db.Integer, primary_key=True)
    po_number = db.Column(db.String(50), unique=True, nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('ASP_suppliers.id'), nullable=False)
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), default=0)
    status = db.Column(db.String(20), default='pending')  # pending, sent, received, cancelled
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    expected_delivery = db.Column(db.DateTime)
    received_date = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('ASP_users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    agency_ref = db.relationship('Agency', backref='purchase_orders', lazy=True)
    creator = db.relationship('User', backref='created_purchase_orders', lazy=True)
    po_items = db.relationship('PurchaseOrderItem', backref='purchase_order', lazy=True, cascade='all, delete-orphan')

class PurchaseOrderItem(db.Model):
    __tablename__ = 'ASP_purchase_order_items'
    id = db.Column(db.Integer, primary_key=True)
    po_id = db.Column(db.Integer, db.ForeignKey('ASP_purchase_orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('ASP_products.id'), nullable=False)
    quantity_ordered = db.Column(db.Integer, nullable=False)
    quantity_received = db.Column(db.Integer, default=0)
    unit_cost = db.Column(db.Numeric(10, 2), nullable=False)
    total_cost = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Relationships
    product = db.relationship('Product', backref='po_items', lazy=True)

class InventoryTransaction(db.Model):
    __tablename__ = 'ASP_inventory_transactions'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('ASP_products.id'), nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # sale, purchase, adjustment, return
    quantity_change = db.Column(db.Integer, nullable=False)  # Positive for increase, negative for decrease
    quantity_before = db.Column(db.Integer, nullable=False)
    quantity_after = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Numeric(10, 2))
    reference_id = db.Column(db.Integer)  # Order ID, PO ID, or Adjustment ID
    reference_type = db.Column(db.String(20))  # order, purchase_order, adjustment
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('ASP_users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    product = db.relationship('Product', backref='inventory_transactions', lazy=True)
    user = db.relationship('User', backref='inventory_transactions', lazy=True)

class StockAdjustment(db.Model):
    __tablename__ = 'ASP_stock_adjustments'
    id = db.Column(db.Integer, primary_key=True)
    adjustment_number = db.Column(db.String(50), unique=True, nullable=False)
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=False)
    reason = db.Column(db.String(100), nullable=False)  # damage, theft, count_correction, etc.
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('ASP_users.id'), nullable=False)
    approved_by = db.Column(db.Integer, db.ForeignKey('ASP_users.id'))
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
    adjustment_id = db.Column(db.Integer, db.ForeignKey('ASP_stock_adjustments.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('ASP_products.id'), nullable=False)
    quantity_before = db.Column(db.Integer, nullable=False)
    quantity_change = db.Column(db.Integer, nullable=False)  # Can be positive or negative
    quantity_after = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(200))
    
    # Relationships
    product = db.relationship('Product', backref='adjustment_items', lazy=True)

class LowStockAlert(db.Model):
    __tablename__ = 'ASP_low_stock_alerts'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('ASP_products.id'), nullable=False)
    threshold_quantity = db.Column(db.Integer, nullable=False)
    current_quantity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='active')  # active, resolved, ignored
    alerted_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
    resolved_by = db.Column(db.Integer, db.ForeignKey('ASP_users.id'))
    
    # Relationships
    product = db.relationship('Product', backref='stock_alerts', lazy=True)
    resolver = db.relationship('User', backref='resolved_alerts', lazy=True)

# Master Data Models
class Category(db.Model):
    __tablename__ = 'ASP_categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=False)
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
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class TaxMaster(db.Model):
    __tablename__ = 'ASP_tax_masters'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    tax_code = db.Column(db.String(20), nullable=False, unique=True)
    tax_rate = db.Column(db.Numeric(5, 2), nullable=False)
    description = db.Column(db.Text)
    agency_id = db.Column(db.Integer, db.ForeignKey('ASP_agencies.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

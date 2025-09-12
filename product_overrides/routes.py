from flask import render_template, request, redirect, url_for, flash, session
from app import db
from auth.utils import login_required, agency_access_required
from utils.decorators import log_activity
from product_overrides import overrides_bp
from models import Product, ProductAgency, Agency, Category, UOM, TaxMaster

@overrides_bp.route('/')
@login_required
@agency_access_required
def list_overrides(current_agency_id=None):
    user_role = session.get('role')
    # Agency admin/staff: fixed to their agency; super_admin: choose agency via filter
    agency_id = request.args.get('agency') if user_role == 'super_admin' else current_agency_id

    query = db.session.query(Product, ProductAgency).join(ProductAgency, ProductAgency.product_id == Product.id)
    if agency_id:
        query = query.filter(ProductAgency.agency_id == agency_id)

    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(db.or_(Product.name.ilike(f'%{search}%'), Product.sku.ilike(f'%{search}%')))

    rows = query.order_by(Product.created_at.desc()).all()

    agencies = Agency.query.all() if user_role == 'super_admin' else Agency.query.filter_by(id=current_agency_id).all()
    return render_template('product_overrides/list.html', rows=rows, agencies=agencies, current_filters={'agency': agency_id, 'search': search})

@overrides_bp.route('/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
@agency_access_required
@log_activity('edit_product_override')
def edit_override(product_id, current_agency_id=None):
    user_role = session.get('role')
    agency_id = request.args.get('agency') if user_role == 'super_admin' else current_agency_id
    if not agency_id:
        flash('Agency is required to edit override', 'error')
        return redirect(url_for('product_overrides.list_overrides'))

    product = Product.query.get_or_404(product_id)
    mapping = ProductAgency.query.filter_by(product_id=product_id, agency_id=agency_id).first()
    if not mapping:
        # Create mapping if missing
        mapping = ProductAgency(product_id=product_id, agency_id=agency_id, is_active=True)
        db.session.add(mapping)
        db.session.flush()

    if request.method == 'POST':
        # Text and dropdowns
        mapping.display_name = request.form.get('display_name') or None
        mapping.category_id = int(request.form.get('category_id')) if request.form.get('category_id') else None
        mapping.uom_id = int(request.form.get('uom_id')) if request.form.get('uom_id') else None
        mapping.tax_master_id = int(request.form.get('tax_master_id')) if request.form.get('tax_master_id') else None
        mapping.is_active = request.form.get('is_active') == 'on'

        # Numeric fields (optional overrides)
        def parse_optional_decimal(val):
            try:
                return float(val) if val not in (None, '',) else None
            except ValueError:
                return None

        mapping.buy_price = parse_optional_decimal(request.form.get('buy_price'))
        mapping.sell_price = parse_optional_decimal(request.form.get('sell_price'))
        mapping.mrp_price = parse_optional_decimal(request.form.get('mrp_price'))

        db.session.commit()
        flash('Product override saved', 'success')
        return redirect(url_for('product_overrides.list_overrides', agency=agency_id))

    categories = Category.query.filter_by(is_active=True).all()
    uoms = UOM.query.filter_by(is_active=True).all()
    tax_masters = TaxMaster.query.filter_by(is_active=True).all()
    return render_template('product_overrides/form.html', product=product, mapping=mapping, categories=categories, uoms=uoms, tax_masters=tax_masters, agency_id=agency_id)
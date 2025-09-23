from flask import render_template, request, redirect, url_for, flash, session
from app import db
from auth.utils import login_required, permission_required
from utils.decorators import log_activity
from product_overrides import overrides_bp
from models import Product, ProductAgency, Agency, Category, UOM, TaxMaster
from sqlalchemy import func, or_, and_

@overrides_bp.route('/')
@login_required
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def list_overrides(current_agency_id=None):
    user_role = session.get('role')
    # Build filters (super_admin can choose agency; others are fixed)
    filters = {
        'agency': request.args.get('agency') if user_role == 'super_admin' else current_agency_id,
        'search': (request.args.get('search') or '').strip(),
        'category': request.args.get('category') or '',
        'status': request.args.get('status') or '',
        'date_from': request.args.get('date_from') or '',
        'date_to': request.args.get('date_to') or ''
    }

    query = db.session.query(Product, ProductAgency).join(ProductAgency, ProductAgency.product_id == Product.id)

    # Agency filter
    if filters['agency']:
        query = query.filter(ProductAgency.agency_id == filters['agency'])

    # Search by name or SKU
    if filters['search']:
        s = f"%{filters['search']}%"
        query = query.filter(or_(Product.name.ilike(s), Product.sku.ilike(s)))

    # Category filter (effective category: override or product default)
    if filters['category']:
        try:
            cat_id = int(filters['category'])
            query = query.filter(func.coalesce(ProductAgency.category_id, Product.category_id) == cat_id)
        except (TypeError, ValueError):
            pass

    # Status filter (mapping active/inactive)
    if filters['status'] == 'active':
        query = query.filter(ProductAgency.is_active.is_(True))
    elif filters['status'] == 'inactive':
        query = query.filter(ProductAgency.is_active.is_(False))

    # Date range on mapping creation date
    from datetime import datetime, timedelta
    if filters['date_from']:
        try:
            dt_from = datetime.strptime(filters['date_from'], '%Y-%m-%d')
            query = query.filter(ProductAgency.created_at >= dt_from)
        except ValueError:
            pass
    if filters['date_to']:
        try:
            dt_to = datetime.strptime(filters['date_to'], '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(ProductAgency.created_at < dt_to)
        except ValueError:
            pass

    rows = query.order_by(Product.created_at.desc()).all()

    # Dropdown data
    agencies = Agency.query.all() if user_role == 'super_admin' else Agency.query.filter_by(id=current_agency_id).all()
    categories = Category.query.filter_by(is_active=True).all()

    return render_template(
        'product_overrides/list.html',
        rows=rows,
        agencies=agencies,
        categories=categories,
        filters=filters
    )

@overrides_bp.route('/add', methods=['GET', 'POST'])
@login_required
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager'])
@log_activity('add_product_override')
def add_override(current_agency_id=None):
    """Add a product mapping to an agency, then redirect to edit overrides"""
    user_role = session.get('role')
    # For super_admin allow agency selection; for others use current agency
    selected_agency_id = request.values.get('agency') if user_role == 'super_admin' else current_agency_id

    if request.method == 'POST':
        agency_id = int(request.form.get('agency_id')) if user_role == 'super_admin' else current_agency_id
        selected_product_id = request.form.get('selected_product_id')
        product_id = selected_product_id or request.form.get('product_id')
        if not agency_id:
            flash('Please select an agency.', 'error')
            return redirect(url_for('product_overrides.add_override', agency=selected_agency_id))
        if not product_id:
            flash('Please select a product.', 'error')
            return redirect(url_for('product_overrides.add_override', agency=agency_id))
        try:
            product_id = int(product_id)
        except (TypeError, ValueError):
            flash('Invalid product selected.', 'error')
            return redirect(url_for('product_overrides.add_override', agency=agency_id))

        product = Product.query.get(product_id)
        if not product:
            flash('Invalid product selected.', 'error')
            return redirect(url_for('product_overrides.add_override', agency=agency_id))

        mapping = ProductAgency.query.filter_by(product_id=product.id, agency_id=agency_id).first()
        if mapping:
            # Reactivate if needed and go to edit
            if not mapping.is_active:
                mapping.is_active = True
                db.session.commit()
            flash('Product is already mapped to this agency. You can edit its overrides now.', 'info')
            return redirect(url_for('product_overrides.edit_override', product_id=product.id, agency=agency_id))

        # Create mapping
        mapping = ProductAgency(product_id=product.id, agency_id=agency_id, is_active=True)
        db.session.add(mapping)
        db.session.commit()
        flash('Product added to agency successfully. You can now set overrides.', 'success')
        return redirect(url_for('product_overrides.edit_override', product_id=product.id, agency=agency_id))

    # GET -> show selection form
    agencies = Agency.query.all() if user_role == 'super_admin' else Agency.query.filter_by(id=current_agency_id).all()

    # If super_admin hasn’t selected an agency yet, show a minimal page to pick one
    products = []
    if selected_agency_id:
        # Products not yet mapped to the selected agency (or inactive mapping allowed to re-add via POST)
        from sqlalchemy import and_
        products = db.session.query(Product).outerjoin(
            ProductAgency,
            and_(ProductAgency.product_id == Product.id, ProductAgency.agency_id == int(selected_agency_id))
        ).filter(Product.is_active == True, ProductAgency.id.is_(None)).order_by(Product.name).limit(200).all()

    return render_template('product_overrides/add.html', agencies=agencies, selected_agency_id=selected_agency_id, products=products)

@overrides_bp.route('/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager'])
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
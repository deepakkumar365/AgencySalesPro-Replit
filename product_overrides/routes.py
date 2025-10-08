from flask import render_template, request, redirect, url_for, flash, session, send_file
import pandas as pd
import io
from app import db
from auth.utils import login_required, permission_required
from utils.decorators import log_activity
from product_overrides import overrides_bp
from models import Product, ProductAgency, Agency, Category, UOM, TaxMaster
from sqlalchemy import func, or_, and_


@overrides_bp.route('/')
@login_required
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff', 'salesperson'])
def list_overrides(current_agency_id=None):
    user_role = session.get('role')
    agency_from_url = request.args.get('agency')

    # Build filters (super_admin can choose agency; others are fixed)
    filters = {
        'agency': agency_from_url if user_role == 'super_admin' else current_agency_id,
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

@overrides_bp.route('/bulk-upload', methods=['GET', 'POST'])
@login_required
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager'])
@log_activity('bulk_upload_overrides')
def bulk_upload_overrides(current_agency_id=None):
    user_role = session.get('role')
    user_id = session.get('user_id')
    
    # Determine agency context
    agency_id = request.values.get('agency', type=int)
    if user_role == 'agency_admin':
        agency_id = current_agency_id
    
    if request.method == 'POST':
        if not agency_id:
            flash('Please select an agency before uploading.', 'danger')
            return redirect(url_for('product_overrides.bulk_upload_overrides'))

        if 'file' not in request.files or not request.files['file'].filename:
            flash('No file selected for upload.', 'error')
            return redirect(request.url)

        file = request.files['file']
        if not file.filename.lower().endswith(('.csv', '.xlsx')):
            flash('Invalid file format. Please upload a CSV or Excel file.', 'error')
            return redirect(request.url)

        try:
            df = pd.read_excel(file) if file.filename.lower().endswith('.xlsx') else pd.read_csv(file)
            df.columns = [c.lower().strip() for c in df.columns] # Normalize column names

            required_columns = ['sku', 'display_name', 'category_name', 'uom_name']
            if not all(col in df.columns for col in required_columns):
                flash(f'File must contain required columns: {", ".join(required_columns)}.', 'error')
                return redirect(request.url)

            success_count = 0
            created_count = 0
            updated_count = 0
            error_count = 0
            errors = []

            # Pre-fetch master data for lookups to avoid querying in a loop
            categories = {c.name.lower(): c.id for c in Category.query.all()}
            uoms = {u.name.lower(): u.id for u in UOM.query.all()}
            tax_masters = {t.name.lower(): t.id for t in TaxMaster.query.all()}

            for index, row in df.iterrows():
                try:
                    sku = str(row.get('sku', '')).strip().upper()
                    display_name = str(row.get('display_name', '')).strip()

                    if not sku or not display_name:
                        errors.append(f"Row {index+2}: SKU and display_name are required.")
                        error_count += 1
                        continue

                    product = Product.query.filter_by(sku=sku).first()

                    if not product: # Product does not exist, create it
                        # For new products, these are required
                        category_name = str(row.get('category_name', '')).strip()
                        uom_name = str(row.get('uom_name', '')).strip()
                        tax_name = str(row.get('tax_name', '')).strip() # Optional
                        hsn_code = str(row.get('hsn_code', '')).strip() if pd.notna(row.get('hsn_code')) else None
                        item_code = str(row.get('item_code', '')).strip() if pd.notna(row.get('item_code')) else None

                        if not all([category_name, uom_name]):
                            errors.append(f"Row {index+2}: category_name and uom_name are required for new product '{sku}'.")
                            error_count += 1
                            continue
                        
                        buy_price = float(row.get('buy_price', 0.0))
                        sell_price = float(row.get('sell_price', 0.0))
                        mrp_price = float(row.get('mrp_price', 0.0))
                        margin = round(((sell_price - buy_price) / buy_price) * 100, 2) if buy_price > 0 else 0

                        product = Product(
                            name=display_name, # Use display_name as master name for new products
                            sku=sku,
                            buy_price=buy_price,
                            sell_price=sell_price,
                            mrp_price=mrp_price,
                            margin=margin,
                            category_id=categories.get(category_name.lower()),
                            uom_id=uoms.get(uom_name.lower()),
                            tax_master_id=tax_masters.get(tax_name.lower()) if tax_name else None,
                            hsn_code=hsn_code,
                            item_code=item_code,
                            is_active=True
                        )
                        db.session.add(product)
                        db.session.flush() # To get product.id
                        created_count += 1
                    else:
                        updated_count += 1

                    # Find or create the agency mapping
                    mapping = ProductAgency.query.filter_by(product_id=product.id, agency_id=agency_id).first()
                    if not mapping:
                        mapping = ProductAgency(product_id=product.id, agency_id=agency_id)
                        db.session.add(mapping)

                    # Update mapping fields from the file if they exist in the row
                    # For existing products, display_name is an override.
                    if 'display_name' in row and pd.notna(row['display_name']):
                        mapping.display_name = str(row['display_name'])

                    # Prices are always overrides
                    if 'buy_price' in row and pd.notna(row['buy_price']): mapping.buy_price = float(row['buy_price'])
                    if 'sell_price' in row and pd.notna(row['sell_price']): mapping.sell_price = float(row['sell_price'])
                    if 'mrp_price' in row and pd.notna(row['mrp_price']): mapping.mrp_price = float(row['mrp_price'])
                    
                    # is_active defaults to True for the mapping
                    is_active_val = row.get('is_active')
                    if pd.notna(is_active_val):
                        mapping.is_active = bool(is_active_val)
                    else:
                        mapping.is_active = True

                    # Attribute overrides
                    if 'category_name' in row and pd.notna(row['category_name']):
                        mapping.category_id = categories.get(str(row['category_name']).lower())
                    if 'uom_name' in row and pd.notna(row['uom_name']):
                        mapping.uom_id = uoms.get(str(row['uom_name']).lower())
                    if 'tax_name' in row and pd.notna(row['tax_name']):
                        mapping.tax_master_id = tax_masters.get(str(row['tax_name']).lower())

                    success_count += 1
                
                except Exception as e:
                    errors.append(f"Row {index+2}: Error processing - {str(e)}")
                    error_count += 1
                    db.session.rollback() # Rollback this row's transaction

            db.session.commit()
            flash_msg = f'Bulk process finished. Products Created: {created_count}, Mappings Updated: {updated_count}, Failures: {error_count}.'
            flash(flash_msg, 'success')
            if errors:
                flash("Errors: " + " | ".join(errors[:5]), 'danger')

        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred during processing: {str(e)}', 'danger')
        
        return redirect(url_for('product_overrides.bulk_upload_overrides', agency=agency_id))
    
    # Determine which agencies the user can select from
    agencies = []
    if user_role == 'super_admin':
        agencies = Agency.query.filter_by(is_active=True).order_by(Agency.name).all()
    elif user_role == 'agency_manager':
        agencies = Agency.query.filter_by(agency_manager_id=user_id, is_active=True).order_by(Agency.name).all()
    
    selected_agency = Agency.query.get(agency_id) if agency_id else None
    
    return render_template('product_overrides/bulk_upload.html', 
                           agencies=agencies,
                           selected_agency_id=agency_id,
                           selected_agency=selected_agency)

@overrides_bp.route('/download-template')
@login_required
def download_overrides_template():
    """Provides a CSV template for bulk override uploads."""
    columns = [
        'sku', 'display_name', 'buy_price', 'sell_price', 'mrp_price',
        'category_name', 'uom_name', 'tax_name', 'hsn_code', 'item_code', 'is_active'
    ]
    
    example_data = [[
        'PROD-SKU-001', 'Agency Specific Name', 100.00, 150.00, 160.00,
        'Electronics', 'Pieces', 'GST 18%', '8517', 'ITEM001', True
    ]]
    
    df = pd.DataFrame(example_data, columns=columns)
    
    output = io.BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)
    
    return send_file(output, mimetype='text/csv', as_attachment=True, download_name='product_overrides_template.csv')
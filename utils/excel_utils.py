import io
import csv
from datetime import datetime
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.styles import Font, PatternFill
from extensions import db
from models import Product, Order, OrderItem, ProductAgency, Agency

def export_products_to_excel(products):
    """Export products to Excel file using openpyxl"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Products"
    
    # Headers
    headers = ['ID', 'Name', 'Description', 'SKU', 'Sell Price (Effective)', 'Buy Cost', 'Category (Effective)', 'Agency', 'Active (Mapping)', 'Created At']
    ws.append(headers)
    
    # Style headers
    header_font = Font(bold=True)
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
    
    # Add data
    for product in products:
        # Find mapping for given agency context if provided by caller; otherwise, try to use the first mapping
        mapping = None
        if hasattr(product, 'agency_mappings') and product.agency_mappings:
            mapping = product.agency_mappings[0]
        effective_sell = float(mapping.sell_price) if mapping and mapping.sell_price is not None else float(product.sell_price or 0)
        effective_category_name = (
            (mapping.category_ref.name if mapping and mapping.category_ref else None)
            or (product.category_ref.name if hasattr(product, 'category_ref') and product.category_ref else None)
            or (product.category if hasattr(product, 'category') else None)
        )
        agency_name = mapping.agency.name if mapping else ''
        mapping_active = mapping.is_active if mapping else True
        row_data = [
            product.id,
            product.name,
            product.description,
            product.sku,
            effective_sell,
            float(product.buy_price) if product.buy_price else 0,
            effective_category_name or '-',
            agency_name,
            mapping_active,
            product.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ]
        ws.append(row_data)
    
    # Auto-size columns
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column_letter].width = adjusted_width
    
    # Save to BytesIO
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output

def import_products_from_excel(file, agency_id, user_role):
    """Import products from Excel or CSV file"""
    try:
        imported = 0
        skipped = 0
        
        if file.filename.lower().endswith('.csv'):
            # Handle CSV file
            content = file.read().decode('utf-8')
            csv_file = io.StringIO(content)
            reader = csv.DictReader(csv_file)
            
            for row in reader:
                # Extract data from row
                name = row.get('Name') or row.get('name') or ''
                sku = row.get('SKU') or row.get('sku') or ''
                price = row.get('Price') or row.get('price') or ''
                
                if not all([name.strip(), sku.strip(), price]):
                    skipped += 1
                    continue
                
                # Check if SKU already exists (global)
                if Product.query.filter_by(sku=sku.strip()).first():
                    skipped += 1
                    continue
                
                # Create product master and mapping
                try:
                    buy = float(row.get('Cost', 0)) if row.get('Cost') else 0
                    sell = float(price)
                    mrp = float(row.get('MRP', sell)) if row.get('MRP') else sell
                    margin = round(((sell - buy) / buy) * 100, 2) if buy > 0 else 0

                    product = Product(
                        name=name.strip(),
                        description=row.get('Description', '').strip(),
                        sku=sku.strip(),
                        buy_price=buy,
                        sell_price=sell,
                        mrp_price=mrp,
                        margin=margin,
                        is_active=True
                    )
                    db.session.add(product)
                    db.session.flush()

                    mapping = ProductAgency(
                        product_id=product.id,
                        agency_id=agency_id,
                        is_active=True
                    )
                    db.session.add(mapping)
                    imported += 1
                except (ValueError, TypeError):
                    skipped += 1
                    continue
        
        else:
            # Handle Excel file using openpyxl
            from openpyxl import load_workbook
            
            wb = load_workbook(file)
            ws = wb.active
            
            # Get headers from first row
            headers = []
            for cell in ws[1]:
                headers.append(cell.value)
            
            # Process data rows
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not any(row):  # Skip empty rows
                    continue
                
                # Create row dictionary
                row_dict = {}
                for i, value in enumerate(row):
                    if i < len(headers) and headers[i]:
                        row_dict[headers[i]] = value
                
                # Extract data from row
                name = row_dict.get('Name') or row_dict.get('name') or ''
                sku = row_dict.get('SKU') or row_dict.get('sku') or ''
                price = row_dict.get('Price') or row_dict.get('price') or ''
                
                if not all([str(name).strip(), str(sku).strip(), price]):
                    skipped += 1
                    continue
                
                # Check if SKU already exists (global)
                if Product.query.filter_by(sku=str(sku).strip()).first():
                    skipped += 1
                    continue
                
                # Create product master and mapping
                try:
                    buy = float(row_dict.get('Cost', 0)) if row_dict.get('Cost') else 0
                    sell = float(price)
                    mrp = float(row_dict.get('MRP', sell)) if row_dict.get('MRP') else sell
                    margin = round(((sell - buy) / buy) * 100, 2) if buy > 0 else 0

                    product = Product(
                        name=str(name).strip(),
                        description=str(row_dict.get('Description', '')).strip(),
                        sku=str(sku).strip(),
                        buy_price=buy,
                        sell_price=sell,
                        mrp_price=mrp,
                        margin=margin,
                        is_active=True
                    )
                    
                    db.session.add(product)
                    db.session.flush()

                    mapping = ProductAgency(
                        product_id=product.id,
                        agency_id=agency_id,
                        is_active=True
                    )
                    db.session.add(mapping)
                    imported += 1
                except (ValueError, TypeError):
                    skipped += 1
                    continue
        
        db.session.commit()
        
        return {
            'success': True,
            'imported': imported,
            'skipped': skipped
        }
        
    except Exception as e:
        db.session.rollback()
        return {
            'success': False,
            'message': str(e)
        }

def export_orders_to_excel(orders):
    """Export orders to Excel file using openpyxl"""
    wb = Workbook()
    
    # Orders details sheet
    ws_details = wb.active
    ws_details.title = "Order Details"
    
    # Headers for details
    detail_headers = [
        'Order ID', 'Order Number', 'Customer', 'Customer Email', 'Customer Phone',
        'Location', 'Agency', 'Salesperson', 'Product Name', 'Product SKU',
        'Quantity', 'Unit Price', 'Total Price', 'Order Status', 'Order Total',
        'Discount', 'Tax', 'Order Date', 'Delivery Date', 'Notes'
    ]
    ws_details.append(detail_headers)
    
    # Style headers
    header_font = Font(bold=True)
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    
    for cell in ws_details[1]:
        cell.font = header_font
        cell.fill = header_fill
    
    # Add order details data
    for order in orders:
        for item in order.order_items:
            row_data = [
                order.id,
                order.order_number,
                order.customer.name,
                order.customer.email,
                order.customer.phone,
                order.customer.location.name,
                order.agency.name,
                order.salesperson.full_name,
                item.product.name,
                item.product.sku,
                item.quantity,
                float(item.unit_price),
                float(item.total_price),
                order.status,
                float(order.total_amount),
                float(order.discount),
                float(order.tax),
                order.order_date.strftime('%Y-%m-%d %H:%M:%S'),
                order.delivery_date.strftime('%Y-%m-%d') if order.delivery_date else '',
                order.notes
            ]
            ws_details.append(row_data)
    
    # Auto-size columns for details
    for column in ws_details.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws_details.column_dimensions[column_letter].width = adjusted_width
    
    # Order summary sheet
    ws_summary = wb.create_sheet("Order Summary")
    summary_headers = [
        'Order Number', 'Customer', 'Agency', 'Salesperson', 'Status',
        'Total Amount', 'Order Date', 'Items Count'
    ]
    ws_summary.append(summary_headers)
    
    # Style summary headers
    for cell in ws_summary[1]:
        cell.font = header_font
        cell.fill = header_fill
    
    # Add summary data
    order_summary = {}
    for order in orders:
        if order.id not in order_summary:
            row_data = [
                order.order_number,
                order.customer.name,
                order.agency.name,
                order.salesperson.full_name,
                order.status,
                float(order.total_amount),
                order.order_date.strftime('%Y-%m-%d %H:%M:%S'),
                len(order.order_items)
            ]
            ws_summary.append(row_data)
            order_summary[order.id] = True
    
    # Auto-size columns for summary
    for column in ws_summary.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws_summary.column_dimensions[column_letter].width = adjusted_width
    
    # Save to BytesIO
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output
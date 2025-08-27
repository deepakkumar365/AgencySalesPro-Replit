import pandas as pd
import io
from app import db
from models import Product, Order, OrderItem

def export_products_to_excel(products):
    """Export products to Excel file"""
    data = []
    for product in products:
        data.append({
            'ID': product.id,
            'Name': product.name,
            'Description': product.description,
            'SKU': product.sku,
            'Price': float(product.price),
            'Cost': float(product.cost) if product.cost else 0,
            'Stock Quantity': product.stock_quantity,
            'Category': product.category,
            'Agency': product.agency.name,
            'Active': product.is_active,
            'Created At': product.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    df = pd.DataFrame(data)
    
    # Create Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Products', index=False)
    
    output.seek(0)
    return output

def import_products_from_excel(file, agency_id, user_role):
    """Import products from Excel file"""
    try:
        # Read Excel file
        if file.filename.lower().endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        
        imported = 0
        skipped = 0
        
        for _, row in df.iterrows():
            # Extract data from row
            name = row.get('Name') or row.get('name')
            sku = row.get('SKU') or row.get('sku')
            price = row.get('Price') or row.get('price')
            
            if not all([name, sku, price]):
                skipped += 1
                continue
            
            # Check if SKU already exists
            if Product.query.filter_by(sku=sku).first():
                skipped += 1
                continue
            
            # Create product
            product = Product(
                name=name,
                description=row.get('Description', ''),
                sku=sku,
                price=float(price),
                cost=float(row.get('Cost', 0)) if row.get('Cost') else 0,
                stock_quantity=int(row.get('Stock Quantity', 0)) if row.get('Stock Quantity') else 0,
                category=row.get('Category', ''),
                agency_id=agency_id,
                is_active=True
            )
            
            db.session.add(product)
            imported += 1
        
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
    """Export orders to Excel file"""
    data = []
    for order in orders:
        for item in order.order_items:
            data.append({
                'Order ID': order.id,
                'Order Number': order.order_number,
                'Customer': order.customer.name,
                'Customer Email': order.customer.email,
                'Customer Phone': order.customer.phone,
                'Location': order.customer.location.name,
                'Agency': order.agency.name,
                'Salesperson': order.salesperson.full_name,
                'Product Name': item.product.name,
                'Product SKU': item.product.sku,
                'Quantity': item.quantity,
                'Unit Price': float(item.unit_price),
                'Total Price': float(item.total_price),
                'Order Status': order.status,
                'Order Total': float(order.total_amount),
                'Discount': float(order.discount),
                'Tax': float(order.tax),
                'Order Date': order.order_date.strftime('%Y-%m-%d %H:%M:%S'),
                'Delivery Date': order.delivery_date.strftime('%Y-%m-%d') if order.delivery_date else '',
                'Notes': order.notes
            })
    
    df = pd.DataFrame(data)
    
    # Create Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Orders', index=False)
        
        # Create summary sheet
        summary_data = []
        order_summary = {}
        for order in orders:
            if order.id not in order_summary:
                order_summary[order.id] = {
                    'Order Number': order.order_number,
                    'Customer': order.customer.name,
                    'Agency': order.agency.name,
                    'Salesperson': order.salesperson.full_name,
                    'Status': order.status,
                    'Total Amount': float(order.total_amount),
                    'Order Date': order.order_date.strftime('%Y-%m-%d %H:%M:%S'),
                    'Items Count': len(order.order_items)
                }
        
        summary_df = pd.DataFrame(list(order_summary.values()))
        summary_df.to_excel(writer, sheet_name='Order Summary', index=False)
    
    output.seek(0)
    return output

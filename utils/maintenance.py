"""
Maintenance utilities for AgencySales Pro.

This module provides utility functions for data maintenance tasks,
such as resyncing product names in order items.
"""

def resync_product_names():
    """
    Resync all item product names across all transactional tables to respect current ProductAgency overrides.
    
    This function iterates through all order items, purchase order items, invoice items, and
    delivery challan items, updating their product_name field with the effective display name
    from the respective entity's agency context.
    
    Returns:
        dict: Statistics including:
            - total_updated: Total number of records updated
            - order_items_updated: Order items updated
            - po_items_updated: Purchase order items updated
            - invoice_items_updated: Invoice items updated
            - challan_items_updated: Delivery challan items updated
            - errors: List of error messages
        
    Raises:
        Exception: If there's an error during the resync process
    """
    from models import OrderItem, Order, Product, PurchaseOrderItem, PurchaseOrder, InvoiceItem, Invoice, DeliveryChallanItem, DeliveryChallan
    from extensions import db
    
    stats = {
        'total_updated': 0,
        'order_items_updated': 0,
        'po_items_updated': 0,
        'invoice_items_updated': 0,
        'challan_items_updated': 0,
        'errors': []
    }
    
    try:
        # Resync OrderItems
        order_items = OrderItem.query.all()
        for item in order_items:
            try:
                if item.product and item.order:
                    effective_name = item.product.get_display_name_for_agency(item.order.agency_id)
                    if item.product_name != effective_name:
                        item.product_name = effective_name
                        stats['order_items_updated'] += 1
                        stats['total_updated'] += 1
            except Exception as e:
                stats['errors'].append(f"Error processing OrderItem {item.id}: {str(e)}")
        
        # Resync PurchaseOrderItems
        po_items = PurchaseOrderItem.query.all()
        for item in po_items:
            try:
                if item.product and item.purchase_order:
                    effective_name = item.product.get_display_name_for_agency(item.purchase_order.agency_id)
                    if item.product_name != effective_name:
                        item.product_name = effective_name
                        stats['po_items_updated'] += 1
                        stats['total_updated'] += 1
            except Exception as e:
                stats['errors'].append(f"Error processing PurchaseOrderItem {item.id}: {str(e)}")
        
        # Resync InvoiceItems
        invoice_items = InvoiceItem.query.all()
        for item in invoice_items:
            try:
                if item.product and item.invoice:
                    effective_name = item.product.get_display_name_for_agency(item.invoice.agency_id)
                    if item.product_name != effective_name:
                        item.product_name = effective_name
                        stats['invoice_items_updated'] += 1
                        stats['total_updated'] += 1
            except Exception as e:
                stats['errors'].append(f"Error processing InvoiceItem {item.id}: {str(e)}")
        
        # Resync DeliveryChallanItems
        challan_items = DeliveryChallanItem.query.all()
        for item in challan_items:
            try:
                if item.product and item.challan:
                    effective_name = item.product.get_display_name_for_agency(item.challan.agency_id)
                    if item.product_name != effective_name:
                        item.product_name = effective_name
                        stats['challan_items_updated'] += 1
                        stats['total_updated'] += 1
            except Exception as e:
                stats['errors'].append(f"Error processing DeliveryChallanItem {item.id}: {str(e)}")
        
        # Commit all changes at once
        db.session.commit()
        
        return stats
        
    except Exception as e:
        db.session.rollback()
        raise Exception(f"Failed to resync product names: {str(e)}")
"""
Service/Garage utility functions for work order and inventory management.
"""
from decimal import Decimal
from datetime import datetime
import logging
from extensions import db
from models import InventoryTransaction, WorkOrderLineItem

logger = logging.getLogger(__name__)


def deduct_inventory_for_work_order(work_order, user_id):
    """
    Deduct inventory for all material items in a completed work order.
    
    Atomically processes all materials - either all succeed or all are rolled back.
    Idempotent: calling multiple times with same work order is safe.
    
    Args:
        work_order: WorkOrder instance to finalize
        user_id: ID of the user performing the finalization
        
    Returns:
        dict: {
            'success': bool,
            'message': str,
            'deducted_items': list of {'product_id', 'quantity', 'transaction_id'},
            'errors': list of error messages if any,
            'skipped_items': int, count of items already deducted
        }
    """
    deducted_items = []
    errors = []
    skipped_count = 0
    
    # Validate inputs
    if not work_order:
        logger.error("deduct_inventory_for_work_order: work_order is None")
        return {
            'success': False,
            'message': 'Invalid work order',
            'deducted_items': [],
            'errors': ['Work order is required'],
            'skipped_items': 0
        }
    
    if not user_id:
        logger.error("deduct_inventory_for_work_order: user_id is None")
        return {
            'success': False,
            'message': 'Invalid user ID',
            'deducted_items': [],
            'errors': ['User ID is required'],
            'skipped_items': 0
        }
    
    try:
        # Get all material line items for this work order
        material_items = WorkOrderLineItem.query.filter_by(
            work_order_id=work_order.id,
            line_type='material'
        ).all()
        
        logger.info(f"Processing {len(material_items)} material items for work order {work_order.id}")
        
        # Validate all items first (fail fast on validation)
        validated_items = []
        for line_item in material_items:
            # Skip if already deducted
            if line_item.is_inventory_deducted:
                skipped_count += 1
                logger.debug(f"Line item {line_item.id} already deducted, skipping")
                continue
            
            # Validate product exists
            if not line_item.product_id:
                msg = f"Line item {line_item.id} has no product associated"
                errors.append(msg)
                logger.warning(msg)
                continue
            
            # Determine quantity to deduct
            qty_to_deduct = line_item.consumed_quantity or line_item.quantity
            
            # Validate quantity
            if qty_to_deduct is None:
                msg = f"Line item {line_item.id} has no quantity (consumed: {line_item.consumed_quantity}, estimated: {line_item.quantity})"
                errors.append(msg)
                logger.warning(msg)
                continue
            
            # Convert to Decimal for precision
            try:
                qty_decimal = Decimal(str(qty_to_deduct))
            except (ValueError, TypeError) as e:
                msg = f"Line item {line_item.id} has invalid quantity: {qty_to_deduct}"
                errors.append(msg)
                logger.warning(msg)
                continue
            
            if qty_decimal <= 0:
                msg = f"Line item {line_item.id} has non-positive quantity: {qty_decimal}"
                errors.append(msg)
                logger.warning(msg)
                continue
            
            validated_items.append((line_item, qty_decimal))
        
        # If validation failed and no items validated, return error
        if not validated_items and errors:
            return {
                'success': False,
                'message': 'All material items failed validation',
                'deducted_items': [],
                'errors': errors,
                'skipped_items': skipped_count
            }
        
        # No items to process (all already deducted or no materials)
        if not validated_items:
            msg = 'No material items to deduct from inventory'
            logger.info(f"Work order {work_order.id}: {msg}")
            return {
                'success': True,
                'message': msg,
                'deducted_items': [],
                'errors': [],
                'skipped_items': skipped_count
            }
        
        # Process validated items atomically
        for line_item, qty_decimal in validated_items:
            try:
                # Create inventory transaction for job consumption
                transaction = _create_inventory_transaction(
                    product_id=line_item.product_id,
                    agency_id=work_order.agency_id,
                    transaction_type='job_consumption',
                    quantity_change=-qty_decimal,  # Negative for deduction
                    unit_cost=line_item.unit_cost,
                    reference_id=str(work_order.id),
                    reference_type='work_order',
                    work_order_line_item_id=line_item.id,
                    created_by=user_id,
                    notes=f"Material consumption for work order {work_order.job_number}"
                )
                
                db.session.flush()  # Flush to get transaction ID
                
                # Mark line item as deducted
                line_item.is_inventory_deducted = True
                
                deducted_items.append({
                    'product_id': line_item.product_id,
                    'quantity': float(qty_decimal),
                    'transaction_id': transaction.id
                })
                
                logger.debug(f"Deducted {qty_decimal} units of product {line_item.product_id} for line item {line_item.id}")
                
            except Exception as e:
                # Roll back everything on error (atomic failure)
                db.session.rollback()
                msg = f"Failed to deduct inventory for line item {line_item.id}: {str(e)}"
                errors.append(msg)
                logger.error(msg, exc_info=True)
                
                return {
                    'success': False,
                    'message': f'Transaction failed: {str(e)}',
                    'deducted_items': [],
                    'errors': [msg],
                    'skipped_items': skipped_count
                }
        
        # Commit all changes atomically
        try:
            db.session.commit()
            logger.info(f"Successfully deducted inventory for {len(deducted_items)} items (work order {work_order.id})")
            
            return {
                'success': True,
                'message': f'Successfully deducted inventory for {len(deducted_items)} material items',
                'deducted_items': deducted_items,
                'errors': [],
                'skipped_items': skipped_count
            }
        except Exception as e:
            db.session.rollback()
            msg = f"Failed to commit inventory deductions: {str(e)}"
            logger.error(msg, exc_info=True)
            
            return {
                'success': False,
                'message': msg,
                'deducted_items': [],
                'errors': [msg],
                'skipped_items': skipped_count
            }
            
    except Exception as e:
        db.session.rollback()
        msg = f"Unexpected error during inventory deduction for work order {work_order.id}: {str(e)}"
        logger.error(msg, exc_info=True)
        
        return {
            'success': False,
            'message': msg,
            'deducted_items': [],
            'errors': [msg],
            'skipped_items': skipped_count
        }


def _create_inventory_transaction(product_id, agency_id, transaction_type, quantity_change,
                                  unit_cost, reference_id, reference_type, 
                                  work_order_line_item_id, created_by, notes=None):
    """
    Helper to create an inventory transaction record.
    
    Args:
        product_id: Product ID being transacted
        agency_id: Agency ID context
        transaction_type: Type of transaction ('job_consumption', 'purchase', etc.)
        quantity_change: Quantity change (Decimal or int; negative for deduction)
        unit_cost: Cost per unit (Decimal or float)
        reference_id: ID of the referencing entity (work order ID, order ID, etc.)
        reference_type: Type of reference (work_order, order, purchase_order, etc.)
        work_order_line_item_id: Foreign key to WorkOrderLineItem
        created_by: User ID creating the transaction
        notes: Optional notes; auto-generated if not provided
        
    Returns:
        InventoryTransaction instance (added to session but not committed)
        
    Raises:
        ValueError: If required parameters are missing or invalid
        Exception: Database errors during transaction creation
    """
    # Validate required fields
    if not product_id or not isinstance(product_id, int):
        raise ValueError(f"Invalid product_id: {product_id}")
    if not agency_id or not isinstance(agency_id, int):
        raise ValueError(f"Invalid agency_id: {agency_id}")
    if not transaction_type or not isinstance(transaction_type, str):
        raise ValueError(f"Invalid transaction_type: {transaction_type}")
    if not created_by or not isinstance(created_by, int):
        raise ValueError(f"Invalid created_by: {created_by}")
    
    # Convert quantity_change to Decimal for consistency
    try:
        qty_change_decimal = Decimal(str(quantity_change))
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid quantity_change: {quantity_change}") from e
    
    # Convert unit_cost to Decimal if provided
    unit_cost_decimal = None
    if unit_cost is not None:
        try:
            unit_cost_decimal = Decimal(str(unit_cost))
        except (ValueError, TypeError):
            logger.warning(f"Could not convert unit_cost {unit_cost} to Decimal, using as-is")
            unit_cost_decimal = unit_cost
    
    # Calculate before and after quantities
    current_stock = _get_current_stock(product_id, agency_id)
    quantity_before = Decimal(str(current_stock))
    quantity_after = quantity_before + qty_change_decimal
    
    # Generate default notes if not provided
    if not notes:
        notes = f'{transaction_type} - Ref: {reference_type}#{reference_id}'
    
    # Create transaction record
    transaction = InventoryTransaction(
        product_id=product_id,
        agency_id=agency_id,
        transaction_type=transaction_type,
        quantity_change=qty_change_decimal,
        quantity_before=quantity_before,
        quantity_after=quantity_after,
        unit_cost=unit_cost_decimal,
        reference_id=reference_id,
        reference_type=reference_type,
        work_order_line_item_id=work_order_line_item_id,
        created_by=created_by,
        notes=notes
    )
    
    db.session.add(transaction)
    logger.debug(f"Created inventory transaction: type={transaction_type}, qty={qty_change_decimal}, product={product_id}")
    
    return transaction


def _get_current_stock(product_id, agency_id):
    """
    Calculate current stock level for a product in an agency.
    
    Sums all inventory transactions for the given product and agency combination.
    This represents the net quantity after all purchases, sales, consumption, etc.
    
    Args:
        product_id (int): Product ID to look up
        agency_id (int): Agency ID to look up
        
    Returns:
        Decimal: Current stock quantity (sum of all quantity_change values)
        
    Raises:
        ValueError: If product_id or agency_id is invalid
        Exception: Database errors
        
    Note:
        - Returns 0 if no transactions found (product not yet in inventory)
        - Handles both positive (purchase, adjustment) and negative (consumption, sale) quantities
        - Result is a Decimal for precision in calculations
    """
    from sqlalchemy import func
    
    # Validate inputs
    if not product_id or not isinstance(product_id, int):
        raise ValueError(f"Invalid product_id: {product_id}")
    if not agency_id or not isinstance(agency_id, int):
        raise ValueError(f"Invalid agency_id: {agency_id}")
    
    try:
        result = db.session.query(
            func.sum(InventoryTransaction.quantity_change)
        ).filter(
            InventoryTransaction.product_id == product_id,
            InventoryTransaction.agency_id == agency_id
        ).scalar()
        
        # Convert to Decimal, defaulting to 0 if no transactions
        stock = Decimal(str(result)) if result else Decimal('0')
        
        logger.debug(f"Current stock for product {product_id} in agency {agency_id}: {stock}")
        return stock
        
    except Exception as e:
        logger.error(f"Failed to get current stock for product {product_id}, agency {agency_id}: {str(e)}", exc_info=True)
        raise


def validate_work_order_for_finalization(work_order):
    """
    Validate that a work order can be finalized.
    
    Checks:
    - Work order exists
    - Work order has at least one material item
    - All material items have valid products
    - All material items have quantities
    - Work order is not already finalized
    
    Args:
        work_order: WorkOrder instance to validate
        
    Returns:
        dict: {
            'valid': bool,
            'message': str,
            'errors': list of validation error messages
        }
    """
    errors = []
    
    if not work_order:
        return {
            'valid': False,
            'message': 'Work order does not exist',
            'errors': ['Work order is required']
        }
    
    # Check if already finalized
    if work_order.status == 'Completed' or work_order.is_finalized:
        return {
            'valid': False,
            'message': 'Work order is already finalized',
            'errors': ['Work order has been completed and cannot be re-finalized']
        }
    
    # Get material items
    material_items = WorkOrderLineItem.query.filter_by(
        work_order_id=work_order.id,
        line_type='material'
    ).all()
    
    if not material_items:
        errors.append('Work order has no material items')
    
    for line_item in material_items:
        if not line_item.product_id:
            errors.append(f'Line item {line_item.id} has no product')
        
        qty = line_item.consumed_quantity or line_item.quantity
        if qty is None or qty <= 0:
            errors.append(f'Line item {line_item.id} has invalid quantity: {qty}')
    
    if errors:
        return {
            'valid': False,
            'message': 'Work order validation failed',
            'errors': errors
        }
    
    return {
        'valid': True,
        'message': 'Work order is ready for finalization',
        'errors': []
    }


def get_work_order_material_summary(work_order):
    """
    Get a summary of all materials in a work order.
    
    Args:
        work_order: WorkOrder instance
        
    Returns:
        dict: {
            'total_materials': int,
            'deducted_count': int,
            'pending_count': int,
            'total_estimated_qty': Decimal,
            'total_consumed_qty': Decimal,
            'materials': [
                {
                    'line_item_id': int,
                    'product_id': int,
                    'product_name': str,
                    'estimated_quantity': Decimal,
                    'consumed_quantity': Decimal,
                    'is_deducted': bool,
                    'unit_cost': Decimal
                },
                ...
            ]
        }
    """
    material_items = WorkOrderLineItem.query.filter_by(
        work_order_id=work_order.id,
        line_type='material'
    ).all()
    
    materials = []
    total_estimated = Decimal('0')
    total_consumed = Decimal('0')
    deducted_count = 0
    
    for line_item in material_items:
        estimated = Decimal(str(line_item.quantity or 0))
        consumed = Decimal(str(line_item.consumed_quantity or 0))
        
        total_estimated += estimated
        total_consumed += consumed
        
        if line_item.is_inventory_deducted:
            deducted_count += 1
        
        product_name = line_item.product.name if line_item.product else 'Unknown'
        
        materials.append({
            'line_item_id': line_item.id,
            'product_id': line_item.product_id,
            'product_name': product_name,
            'estimated_quantity': estimated,
            'consumed_quantity': consumed,
            'is_deducted': line_item.is_inventory_deducted,
            'unit_cost': Decimal(str(line_item.unit_cost or 0))
        })
    
    return {
        'total_materials': len(material_items),
        'deducted_count': deducted_count,
        'pending_count': len(material_items) - deducted_count,
        'total_estimated_qty': total_estimated,
        'total_consumed_qty': total_consumed,
        'materials': materials
    }


def can_finalize_work_order(work_order):
    """
    Quick check if a work order can be finalized.
    
    Args:
        work_order: WorkOrder instance
        
    Returns:
        bool: True if work order can be finalized
    """
    if not work_order:
        return False
    
    if hasattr(work_order, 'is_finalized') and work_order.is_finalized:
        return False
    
    if work_order.status == 'Completed':
        return False
    
    material_items = WorkOrderLineItem.query.filter_by(
        work_order_id=work_order.id,
        line_type='material'
    ).count()
    
    return material_items > 0
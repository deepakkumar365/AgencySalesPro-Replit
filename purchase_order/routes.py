from decimal import Decimal, InvalidOperation
from datetime import datetime

import uuid
from flask import render_template, request, redirect, url_for, flash, session, jsonify
from sqlalchemy import or_, func

from app import db
from models import (
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
    InventoryTransaction,
    Product,
    Agency,
    User,
    Location,
)
from purchase_order import purchase_order_bp
from auth.utils import login_required, permission_required
from utils.decorators import log_activity


@purchase_order_bp.route("/")
@permission_required(roles=["super_admin", "agency_admin", "agency_manager", "staff"])
def list_purchase_orders(current_agency_id=None):
    """List purchase orders with optional filtering by agency."""
    user_role = session.get("role")
    user_id = session.get("user_id")

    query = PurchaseOrder.query
    if user_role == "super_admin":
        agency_filter = request.args.get("agency")
        if agency_filter:
            query = query.filter(PurchaseOrder.agency_id == agency_filter)
    else:
        query = query.filter(PurchaseOrder.agency_id == current_agency_id)

    supplier_filter = request.args.get("supplier")
    status_filter = request.args.get("status")

    if supplier_filter:
        query = query.filter(PurchaseOrder.supplier_id == supplier_filter)

    if status_filter:
        query = query.filter(PurchaseOrder.status == status_filter)

    if user_role == "super_admin":
        agencies = Agency.query.filter_by(is_active=True).all()
        suppliers = Supplier.query.filter_by(is_active=True).all()
    else:
        agencies = []
        suppliers = Supplier.query.filter_by(agency_id=current_agency_id, is_active=True).all()

    purchase_orders = query.order_by(PurchaseOrder.created_at.desc()).paginate(
        page=request.args.get('page', 1, type=int),
        per_page=20,
        error_out=False
    )

    return render_template(
        "purchase_order/list.html",
        purchase_orders=purchase_orders,
        agencies=agencies,
        suppliers=suppliers,
        filters={
            "agency": request.args.get("agency"),
            "supplier": supplier_filter,
            "status": status_filter,
        },
    )


@purchase_order_bp.route("/create", methods=["GET", "POST"])
@login_required
@permission_required(roles=["super_admin", "agency_admin", "agency_manager", "staff"])
@log_activity("create_purchase_order")
def create_purchase_order(current_agency_id=None):
    """Create a new purchase order."""
    if request.method == "POST":
        data = request.form
        supplier_id = data.get("supplier_id")
        status = data.get("status", "draft")
        notes = data.get("notes")

        if session.get("role") == "super_admin":
            agency_id_raw = data.get("agency_id")
            agency_id = int(agency_id_raw) if agency_id_raw else None
        else:
            agency_id = current_agency_id or session.get("agency_id")


        if not agency_id:
            flash("Agency is required.", "danger")
            return redirect(url_for("purchase_order.create_purchase_order"))

        if not supplier_id:
            flash("Supplier is required.", "danger")
            return redirect(url_for("purchase_order.create_purchase_order"))

        po_number = f"PO-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

        purchase_order = PurchaseOrder(
            po_number=po_number,
            supplier_id=supplier_id,
            agency_id=agency_id,
            created_by=session.get("user_id"),
            status=status,
            notes=notes,
        )
        db.session.add(purchase_order)
        db.session.flush()  # get generated ID

        def coerce_decimal(value, default=Decimal("0")):
            try:
                return Decimal(str(value or "0")).quantize(Decimal("0.01"))
            except (InvalidOperation, ValueError, TypeError):
                return default

        subtotal = Decimal("0")

        product_ids = request.form.getlist("product_id[]")
        quantities = request.form.getlist("quantity[]")
        unit_prices = request.form.getlist("unit_price[]")

        for i in range(len(product_ids)):
            product_id = product_ids[i]
            if not product_id:
                continue

            product_id = int(product_id)
            quantity_value = coerce_decimal(quantities[i])
            unit_price_value = coerce_decimal(unit_prices[i])

            if quantity_value <= 0 or unit_price_value < 0:
                continue

            line_total = (quantity_value * unit_price_value).quantize(Decimal("0.01"))
            subtotal += line_total

            purchase_order_item = PurchaseOrderItem(
                po_id=purchase_order.id,
                product_id=product_id,
                quantity_ordered=int(quantity_value),
                unit_cost=unit_price_value,
                total_cost=line_total,
            )
            db.session.add(purchase_order_item)

        purchase_order.total_amount = subtotal

        db.session.commit()
        flash("Purchase order created successfully.", "success")
        return redirect(url_for("purchase_order.list_purchase_orders"))

    user_role = session.get("role")
    if user_role == "super_admin":
        agencies = Agency.query.filter_by(is_active=True).all()
        locations = Location.query.filter_by(is_active=True).all()
        suppliers = Supplier.query.filter_by(is_active=True).all()
    else:
        agency_id = current_agency_id or session.get("agency_id")
        agencies = []
        locations = Location.query.filter_by(agency_id=agency_id, is_active=True).all()
        suppliers = Supplier.query.filter_by(agency_id=agency_id, is_active=True).all()

    product_records = Product.query.filter_by(is_active=True).all()
    products = [
        {
            "id": product.id,
            "name": product.name,
            "sku": product.sku,
            "sell_price": float(product.sell_price or 0),
        }
        for product in product_records
    ]

    return render_template(
        "purchase_order/form.html",
        agencies=agencies,
        suppliers=suppliers,
        locations=locations,
        products=products,
    )


@purchase_order_bp.route("/<int:purchase_order_id>")
@login_required
def view_purchase_order(purchase_order_id):
    """View a specific purchase order."""
    purchase_order = PurchaseOrder.query.get_or_404(purchase_order_id)

    user_role = session.get("role")
    agency_id = session.get("agency_id")

    if user_role != "super_admin" and purchase_order.agency_id != agency_id:
        flash("You do not have permission to view this purchase order.", "danger")
        return redirect(url_for("purchase_order.list_purchase_orders"))

    return render_template("purchase_order/view.html", purchase_order=purchase_order)


@purchase_order_bp.route("/<int:po_id>/receive", methods=["GET", "POST"])
@login_required
@permission_required(roles=["super_admin", "agency_admin", "agency_manager", "staff"])
@log_activity("receive_purchase_order")
def receive_purchase_order(po_id, current_agency_id=None):
    """Receive items against a purchase order and update inventory."""
    po = PurchaseOrder.query.get_or_404(po_id)
    user_role = session.get("role")
    user_id = session.get("user_id")

    # Permission check
    if user_role != "super_admin" and po.agency_id != current_agency_id:
        flash("You do not have permission to receive this purchase order.", "danger")
        return redirect(url_for("purchase_order.list_purchase_orders"))

    if po.status not in ["sent", "partially_received"]:
        flash(f"Cannot receive items for a PO with status '{po.status}'.", "warning")
        return redirect(url_for("purchase_order.view_purchase_order", purchase_order_id=po.id))

    if request.method == "POST":
        try:
            total_quantity_received_in_this_session = 0
            for item in po.po_items:
                received_qty_str = request.form.get(f"quantity_received_{item.id}", "0")
                received_qty = int(received_qty_str)

                if received_qty > 0:
                    total_quantity_received_in_this_session += received_qty

                    # Calculate current stock before this transaction
                    current_stock = db.session.query(func.sum(InventoryTransaction.quantity_change)).filter(
                        InventoryTransaction.product_id == item.product_id
                    ).scalar() or 0

                    # Create inventory transaction
                    transaction = InventoryTransaction(
                        product_id=item.product_id,
                        agency_id=po.agency_id,
                        transaction_type='purchase',
                        quantity_change=received_qty,
                        quantity_before=current_stock,
                        quantity_after=current_stock + received_qty,
                        unit_cost=item.unit_cost,
                        reference_id=po.id,
                        reference_type='purchase_order',
                        notes=f"Received from PO {po.po_number}",
                        created_by=user_id
                    )
                    db.session.add(transaction)

                    # Update the PO item
                    item.quantity_received = (item.quantity_received or 0) + received_qty

            # Update PO status
            total_ordered = sum(item.quantity_ordered for item in po.po_items)
            total_received = sum(item.quantity_received or 0 for item in po.po_items)
            po.status = "received" if total_received >= total_ordered else "partially_received"
            po.received_date = datetime.utcnow()

            db.session.commit()
            flash(f"Received {total_quantity_received_in_this_session} items for PO {po.po_number}.", "success")
            return redirect(url_for("purchase_order.view_purchase_order", purchase_order_id=po.id))
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred: {str(e)}", "danger")

    return render_template("purchase_order/receive.html", purchase_order=po)

@purchase_order_bp.route("/<int:purchase_order_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required(roles=["super_admin", "agency_admin", "agency_manager", "staff"])
@log_activity("edit_purchase_order")
def edit_purchase_order(purchase_order_id, current_agency_id=None):
    """Edit an existing purchase order."""
    purchase_order = PurchaseOrder.query.get_or_404(purchase_order_id)
    user_role = session.get("role")

    # Permission check
    if user_role != "super_admin" and purchase_order.agency_id != current_agency_id:
        flash("You do not have permission to edit this purchase order.", "danger")
        return redirect(url_for("purchase_order.list_purchase_orders"))

    if purchase_order.status not in ["draft", "pending"]:
        flash(f"Cannot edit a purchase order with status '{purchase_order.status}'.", "danger")
        return redirect(url_for("purchase_order.view_purchase_order", purchase_order_id=purchase_order.id))

    if request.method == "POST":
        data = request.form
        supplier_id = data.get("supplier_id")
        status = data.get("status", "draft")
        notes = data.get("notes")

        if not supplier_id:
            flash("Supplier is required.", "danger")
            # Fall through to render form with errors
        else:
            # Update PO fields
            purchase_order.supplier_id = supplier_id
            purchase_order.status = status
            purchase_order.notes = notes

            # Delete existing items to replace them
            PurchaseOrderItem.query.filter_by(po_id=purchase_order.id).delete()

            def coerce_decimal(value, default=Decimal("0")):
                try:
                    return Decimal(str(value or "0")).quantize(Decimal("0.01"))
                except (InvalidOperation, ValueError, TypeError):
                    return default

            subtotal = Decimal("0")
            product_ids = request.form.getlist("product_id[]")
            quantities = request.form.getlist("quantity[]")
            unit_prices = request.form.getlist("unit_price[]")

            for i in range(len(product_ids)):
                product_id = product_ids[i]
                if not product_id:
                    continue

                quantity_value = coerce_decimal(quantities[i])
                unit_price_value = coerce_decimal(unit_prices[i])

                if quantity_value <= 0 or unit_price_value < 0:
                    continue

                line_total = (quantity_value * unit_price_value).quantize(Decimal("0.01"))
                subtotal += line_total

                purchase_order_item = PurchaseOrderItem(
                    po_id=purchase_order.id,
                    product_id=int(product_id),
                    quantity_ordered=int(quantity_value),
                    unit_cost=unit_price_value,
                    total_cost=line_total,
                )
                db.session.add(purchase_order_item)

            purchase_order.total_amount = subtotal
            db.session.commit()
            flash("Purchase order updated successfully.", "success")
            return redirect(url_for("purchase_order.view_purchase_order", purchase_order_id=purchase_order.id))

    # For GET request, prepare data for the form
    if user_role == "super_admin":
        agencies = Agency.query.filter_by(is_active=True).all()
        suppliers = Supplier.query.filter_by(is_active=True).all()
    else:
        agencies = []
        suppliers = Supplier.query.filter_by(agency_id=current_agency_id, is_active=True).all()

    product_records = Product.query.filter_by(is_active=True).all()
    products = [{"id": p.id, "name": p.name, "sku": p.sku, "sell_price": float(p.sell_price or 0)} for p in product_records]
    
    # Create a JSON-serializable list of purchase order items
    po_items_json = [
        {
            "product_id": item.product_id,
            "quantity_ordered": item.quantity_ordered,
            "unit_cost": float(item.unit_cost),
        }
        for item in purchase_order.po_items
    ]

    return render_template(
        "purchase_order/edit.html",
        purchase_order=purchase_order,
        agencies=agencies,
        suppliers=suppliers,
        products=products,
        po_items_json=po_items_json,
    )

@purchase_order_bp.route("/api/search-suppliers")
@login_required
def search_suppliers(current_agency_id=None):
    """Return supplier suggestions for autocomplete."""
    query = (request.args.get("q") or "").strip()

    if not query or len(query) < 2:
        return jsonify([])

    user_role = session.get("role")
    agency_id = current_agency_id or session.get("agency_id")

    supplier_query = Supplier.query
    if user_role != "super_admin":
        supplier_query = supplier_query.filter_by(agency_id=agency_id)

    like_pattern = f"%{query}%"
    supplier_query = supplier_query.filter(
        or_(
            Supplier.name.ilike(like_pattern),
            Supplier.email.ilike(like_pattern),
            Supplier.phone.ilike(like_pattern),
        )
    ).filter_by(is_active=True)

    suppliers = supplier_query.order_by(Supplier.name.asc()).limit(50).all()

    results = [
        {
            "id": supplier.id,
            "name": supplier.name,
            "email": supplier.email,
            "phone": supplier.phone,
        }
        for supplier in suppliers
    ]

    return jsonify(results)
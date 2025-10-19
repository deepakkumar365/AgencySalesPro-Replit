from flask import render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import GarageExpense, WorkOrder, Agency, User
from functools import wraps
from datetime import datetime
from decimal import Decimal
from garage_expenses import garage_expenses_bp

# Authorization decorators
def require_agency_access(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in ['super_admin', 'agency_admin', 'agency_manager', 'service_manager']:
            flash('Unauthorized access', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# EXPENSE TYPES
EXPENSE_TYPES = ['Labour', 'Material', 'Utilities', 'Consumables', 'Other']

# LIST EXPENSES
@garage_expenses_bp.route('/', methods=['GET'])
@login_required
@require_agency_access
def list_expenses():
    """List all expenses"""
    expense_type = request.args.get('expense_type', None)
    work_order_id = request.args.get('work_order_id', None)
    from_date = request.args.get('from_date', None)
    to_date = request.args.get('to_date', None)
    
    query = GarageExpense.query
    
    if current_user.role != 'super_admin':
        query = query.filter_by(agency_id=current_user.agency_id)
    
    if expense_type:
        query = query.filter_by(expense_type=expense_type)
    if work_order_id:
        query = query.filter_by(work_order_id=work_order_id)
    if from_date:
        query = query.filter(GarageExpense.expense_date >= f"{from_date} 00:00:00")
    if to_date:
        query = query.filter(GarageExpense.expense_date <= f"{to_date} 23:59:59")
    
    expenses = query.order_by(GarageExpense.expense_date.desc()).all()
    
    return render_template(
        'garage_expenses/list.html',
        expenses=expenses,
        expense_types=EXPENSE_TYPES,
        current_type=expense_type,
        work_order_id=work_order_id
    )

# CREATE EXPENSE
@garage_expenses_bp.route('/create', methods=['GET', 'POST'])
@login_required
@require_agency_access
def create_expense():
    """Record new expense"""
    work_order_id = request.args.get('work_order_id', None)
    
    if request.method == 'POST':
        data = request.get_json()
        
        # Verify work order access if specified
        if data.get('work_order_id'):
            work_order = WorkOrder.query.get_or_404(data['work_order_id'])
            if current_user.role != 'super_admin' and work_order.agency_id != current_user.agency_id:
                return jsonify({'success': False, 'message': 'Unauthorized'}), 403
            agency_id = work_order.agency_id
        else:
            agency_id = current_user.agency_id if current_user.role != 'super_admin' else data.get('agency_id')
        
        expense = GarageExpense(
            agency_id=agency_id,
            work_order_id=data.get('work_order_id'),
            expense_type=data['expense_type'],
            description=data['description'],
            amount=Decimal(str(data['amount'])),
            recorded_by=current_user.id,
            expense_date=data.get('expense_date', datetime.utcnow())
        )
        db.session.add(expense)
        db.session.commit()
        
        flash('Expense recorded successfully', 'success')
        return jsonify({'success': True, 'expense_id': expense.id})
    
    return render_template(
        'garage_expenses/create.html',
        expense_types=EXPENSE_TYPES,
        work_order_id=work_order_id
    )

# EDIT EXPENSE
@garage_expenses_bp.route('/<int:expense_id>/edit', methods=['GET', 'POST'])
@login_required
@require_agency_access
def edit_expense(expense_id):
    """Edit expense"""
    expense = GarageExpense.query.get_or_404(expense_id)
    
    # Verify access
    if current_user.role != 'super_admin' and expense.agency_id != current_user.agency_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('garage_expenses.list_expenses'))
    
    if request.method == 'POST':
        data = request.get_json()
        expense.expense_type = data['expense_type']
        expense.description = data['description']
        expense.amount = Decimal(str(data['amount']))
        
        db.session.commit()
        flash('Expense updated successfully', 'success')
        return jsonify({'success': True})
    
    return render_template(
        'garage_expenses/edit.html',
        expense=expense,
        expense_types=EXPENSE_TYPES
    )

# DELETE EXPENSE
@garage_expenses_bp.route('/<int:expense_id>/delete', methods=['POST'])
@login_required
@require_agency_access
def delete_expense(expense_id):
    """Delete expense"""
    expense = GarageExpense.query.get_or_404(expense_id)
    
    # Verify access
    if current_user.role != 'super_admin' and expense.agency_id != current_user.agency_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('garage_expenses.list_expenses'))
    
    db.session.delete(expense)
    db.session.commit()
    flash('Expense deleted successfully', 'success')
    
    return redirect(url_for('garage_expenses.list_expenses'))

# EXPENSE REPORT
@garage_expenses_bp.route('/report', methods=['GET'])
@login_required
@require_agency_access
def expense_report():
    """Comprehensive expense report"""
    from_date = request.args.get('from_date', None)
    to_date = request.args.get('to_date', None)
    expense_type = request.args.get('expense_type', None)
    work_order_id = request.args.get('work_order_id', None)
    
    query = GarageExpense.query
    
    if current_user.role != 'super_admin':
        query = query.filter_by(agency_id=current_user.agency_id)
    
    if from_date:
        query = query.filter(GarageExpense.expense_date >= f"{from_date} 00:00:00")
    if to_date:
        query = query.filter(GarageExpense.expense_date <= f"{to_date} 23:59:59")
    if expense_type:
        query = query.filter_by(expense_type=expense_type)
    if work_order_id:
        query = query.filter_by(work_order_id=work_order_id)
    
    expenses = query.order_by(GarageExpense.expense_date.desc()).all()
    
    # Calculate summary by type
    summary = {}
    for expense_type_name in EXPENSE_TYPES:
        total = sum(float(e.amount) for e in expenses if e.expense_type == expense_type_name)
        summary[expense_type_name] = total
    
    total_expenses = sum(float(e.amount) for e in expenses)
    
    return render_template(
        'garage_expenses/report.html',
        expenses=expenses,
        summary=summary,
        total_expenses=total_expenses,
        from_date=from_date,
        to_date=to_date,
        expense_types=EXPENSE_TYPES
    )

# WORK ORDER EXPENSE SUMMARY
@garage_expenses_bp.route('/work-order/<int:work_order_id>/summary', methods=['GET'])
@login_required
def work_order_expense_summary(work_order_id):
    """Get expense summary for work order"""
    work_order = WorkOrder.query.get_or_404(work_order_id)
    
    # Verify access
    if current_user.role != 'super_admin' and work_order.agency_id != current_user.agency_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('index'))
    
    expenses = GarageExpense.query.filter_by(work_order_id=work_order_id).all()
    
    total_by_type = {}
    for expense_type_name in EXPENSE_TYPES:
        total = sum(float(e.amount) for e in expenses if e.expense_type == expense_type_name)
        if total > 0:
            total_by_type[expense_type_name] = total
    
    total_expenses = sum(float(e.amount) for e in expenses)
    
    return render_template(
        'garage_expenses/work_order_summary.html',
        work_order=work_order,
        expenses=expenses,
        total_by_type=total_by_type,
        total_expenses=total_expenses
    )

# API: Get expenses summary
@garage_expenses_bp.route('/api/summary', methods=['GET'])
@login_required
def get_expenses_summary():
    """API endpoint to get expenses summary"""
    from_date = request.args.get('from_date', None)
    to_date = request.args.get('to_date', None)
    
    query = GarageExpense.query
    
    if current_user.role != 'super_admin':
        query = query.filter_by(agency_id=current_user.agency_id)
    
    if from_date:
        query = query.filter(GarageExpense.expense_date >= f"{from_date} 00:00:00")
    if to_date:
        query = query.filter(GarageExpense.expense_date <= f"{to_date} 23:59:59")
    
    expenses = query.all()
    
    summary = {}
    for expense_type_name in EXPENSE_TYPES:
        total = sum(float(e.amount) for e in expenses if e.expense_type == expense_type_name)
        summary[expense_type_name] = total
    
    return jsonify({
        'summary': summary,
        'total': sum(float(e.amount) for e in expenses)
    })

# API: Get expenses for work order
@garage_expenses_bp.route('/api/work-order/<int:work_order_id>/expenses', methods=['GET'])
@login_required
def get_work_order_expenses(work_order_id):
    """API endpoint to get expenses for a work order"""
    expenses = GarageExpense.query.filter_by(work_order_id=work_order_id).all()
    return jsonify([
        {
            'id': e.id,
            'expense_type': e.expense_type,
            'description': e.description,
            'amount': float(e.amount),
            'expense_date': e.expense_date.strftime('%Y-%m-%d %H:%M:%S')
        }
        for e in expenses
    ])
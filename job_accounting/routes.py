from flask import render_template, request, redirect, url_for, flash, session
from sqlalchemy import or_, func
from decimal import Decimal, InvalidOperation

from extensions import db
from models import Job, Customer, User, Agency, JobIncome, JobExpense, PurchaseOrder
from . import job_accounting_bp
from auth.utils import login_required, permission_required
from utils.decorators import log_activity


@job_accounting_bp.route('/dashboard')
@login_required
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def dashboard(**kwargs):
    """Render the job accounting dashboard with comprehensive statistics."""
    user_role = session.get('role')
    current_agency_id = kwargs.get('current_agency_id')
    
    # Base query for jobs
    jobs_query = Job.query
    if user_role != 'super_admin':
        jobs_query = jobs_query.filter(Job.agency_id == current_agency_id)
    
    # Get all jobs
    all_jobs = jobs_query.all()
    
    # Calculate overall statistics
    total_jobs = len(all_jobs)
    active_jobs = len([j for j in all_jobs if j.status == 'active'])
    completed_jobs = len([j for j in all_jobs if j.status == 'completed'])
    
    # Calculate financial totals
    total_income = Decimal('0.00')
    total_expenses = Decimal('0.00')
    total_budget = Decimal('0.00')
    
    for job in all_jobs:
        total_income += job.total_income
        total_expenses += job.total_expenses
        total_budget += job.budget_amount or Decimal('0.00')
    
    net_profit = total_income - total_expenses
    avg_profit_margin = (net_profit / total_income * 100) if total_income > 0 else Decimal('0.00')
    
    # Jobs by status breakdown
    status_breakdown_query = db.session.query(
        Job.status,
        func.count(Job.id).label('count')
    )
    if user_role != 'super_admin':
        status_breakdown_query = status_breakdown_query.filter(Job.agency_id == current_agency_id)
    status_breakdown = status_breakdown_query.group_by(Job.status).all()
    status_breakdown = [{'status': row.status, 'count': row.count} for row in status_breakdown]

    # Jobs by type breakdown
    type_breakdown_query = db.session.query(
        Job.job_type,
        func.count(Job.id).label('count')
    )
    if user_role != 'super_admin':
        type_breakdown_query = type_breakdown_query.filter(Job.agency_id == current_agency_id)
    type_breakdown = type_breakdown_query.group_by(Job.job_type).all()
    type_breakdown = [{'job_type': row.job_type, 'count': row.count} for row in type_breakdown]

    # Income by category breakdown
    income_query = db.session.query(
        JobIncome.category,
        func.sum(JobIncome.amount).label('total')
    ).join(Job).filter(JobIncome.status == 'confirmed')
    if user_role != 'super_admin':
        income_query = income_query.filter(Job.agency_id == current_agency_id)
    income_breakdown = income_query.group_by(JobIncome.category).all()
    income_breakdown = [{'category': row.category, 'total': float(row.total)} for row in income_breakdown]

    # Expense by category breakdown
    expense_query = db.session.query(
        JobExpense.category,
        func.sum(JobExpense.amount).label('total')
    ).join(Job).filter(JobExpense.status == 'confirmed')
    if user_role != 'super_admin':
        expense_query = expense_query.filter(Job.agency_id == current_agency_id)
    expense_breakdown = expense_query.group_by(JobExpense.category).all()
    expense_breakdown = [{'category': row.category, 'total': float(row.total)} for row in expense_breakdown]
    
    # Top 5 profitable jobs
    profitable_jobs = sorted(
        [j for j in all_jobs if j.total_income > 0],
        key=lambda x: x.net_profit,
        reverse=True
    )[:5]
    
    # Top 5 jobs by income
    top_income_jobs = sorted(
        all_jobs,
        key=lambda x: x.total_income,
        reverse=True
    )[:5]
    
    # Recent jobs (last 10)
    recent_jobs = jobs_query.order_by(Job.created_at.desc()).limit(10).all()
    
    # Monthly trend data (last 6 months)
    from datetime import datetime, timedelta
    from dateutil.relativedelta import relativedelta
    
    monthly_data = []
    current_date = datetime.now()
    
    for i in range(5, -1, -1):
        month_date = current_date - relativedelta(months=i)
        month_start = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if i == 0:
            month_end = current_date
        else:
            month_end = (month_start + relativedelta(months=1)) - timedelta(seconds=1)
        
        # Income for the month
        income_query = db.session.query(func.sum(JobIncome.amount)).join(Job).filter(
            JobIncome.status == 'confirmed',
            JobIncome.income_date >= month_start,
            JobIncome.income_date <= month_end
        )
        if user_role != 'super_admin':
            income_query = income_query.filter(Job.agency_id == current_agency_id)
        month_income = income_query.scalar() or Decimal('0.00')
        
        # Expenses for the month
        expense_query = db.session.query(func.sum(JobExpense.amount)).join(Job).filter(
            JobExpense.status == 'confirmed',
            JobExpense.expense_date >= month_start,
            JobExpense.expense_date <= month_end
        )
        if user_role != 'super_admin':
            expense_query = expense_query.filter(Job.agency_id == current_agency_id)
        month_expense = expense_query.scalar() or Decimal('0.00')
        
        monthly_data.append({
            'month': month_start.strftime('%b %Y'),
            'income': float(month_income),
            'expenses': float(month_expense),
            'profit': float(month_income - month_expense)
        })
    
    return render_template(
        'job_accounting/dashboard.html',
        total_jobs=total_jobs,
        active_jobs=active_jobs,
        completed_jobs=completed_jobs,
        total_income=total_income,
        total_expenses=total_expenses,
        total_budget=total_budget,
        net_profit=net_profit,
        avg_profit_margin=avg_profit_margin,
        status_breakdown=status_breakdown,
        type_breakdown=type_breakdown,
        income_breakdown=income_breakdown,
        expense_breakdown=expense_breakdown,
        profitable_jobs=profitable_jobs,
        top_income_jobs=top_income_jobs,
        recent_jobs=recent_jobs,
        monthly_data=monthly_data
    )


@job_accounting_bp.route('/jobs')
@login_required
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def list_jobs(**kwargs):
    user_role = session.get('role')
    current_agency_id = kwargs.get('current_agency_id')
    query = Job.query

    if user_role != 'super_admin':
        query = query.filter(Job.agency_id == current_agency_id)

    search = request.args.get('search')
    status_filter = request.args.get('status')
    job_type_filter = request.args.get('job_type')

    if search:
        query = query.filter(or_(
            Job.job_number.ilike(f'%{search}%'),
            Job.name.ilike(f'%{search}%')
        ))
    if status_filter:
        query = query.filter_by(status=status_filter)
    if job_type_filter:
        query = query.filter_by(job_type=job_type_filter)

    jobs = query.order_by(Job.created_at.desc()).all()

    return render_template(
        'job_accounting/jobs_list.html',
        jobs=jobs,
        search=search,
        status_filter=status_filter,
        job_type_filter=job_type_filter
    )


@job_accounting_bp.route('/jobs/<int:job_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager'])
@log_activity('edit_job')
def edit_job(job_id, **kwargs):
    """Edit an existing job."""
    job = Job.query.get_or_404(job_id)
    user_role = session.get('role')
    current_agency_id = kwargs.get('current_agency_id')

    # Permission check
    if user_role != 'super_admin' and job.agency_id != current_agency_id:
        flash("You do not have permission to edit this job.", "danger")
        return redirect(url_for('job_accounting.list_jobs'))

    if request.method == 'POST':
        data = request.form
        job.name = data.get('name')
        job.description = data.get('description')
        job.job_type = data.get('job_type')
        job.status = data.get('status')
        job.start_date = data.get('start_date') or None
        job.end_date = data.get('end_date') or None

        try:
            job.budget_amount = Decimal(data.get('budget_amount', '0'))
            job.estimated_cost = Decimal(data.get('estimated_cost', '0'))
        except InvalidOperation:
            flash("Invalid amount entered for budget or cost.", "danger")
            # Fall through to render form with errors

        customer_id = data.get('customer_id')
        job.customer_id = int(customer_id) if customer_id else None

        assigned_to = data.get('assigned_to')
        job.assigned_to = int(assigned_to) if assigned_to else None

        db.session.commit()
        flash(f"Job '{job.job_number}' updated successfully.", "success")
        return redirect(url_for('job_accounting.view_job', job_id=job.id))

    # For GET request
    if user_role == 'super_admin':
        agencies = Agency.query.filter_by(is_active=True).all()
        customers = Customer.query.filter_by(is_active=True).all()
        users = User.query.filter(User.is_active == True).all()
    else:
        agencies = []
        customers = Customer.query.join(Customer.agency_mappings).filter(
            Customer.is_active == True,
            Customer.agency_mappings.any(agency_id=current_agency_id)
        ).all()
        users = User.query.filter(User.is_active == True, User.agency_id == current_agency_id).all()

    return render_template(
        "job_accounting/form.html",
        form_title="Edit Job",
        job=job,
        agencies=agencies,
        customers=customers,
        users=users
    )

@job_accounting_bp.route('/jobs/<int:job_id>')
@login_required
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def view_job(job_id, **kwargs):
    """View a single job's details."""
    job = Job.query.get_or_404(job_id)
    user_role = session.get('role')
    current_agency_id = kwargs.get('current_agency_id')

    # Permission check
    if user_role != 'super_admin' and job.agency_id != current_agency_id:
        flash("You do not have permission to view this job.", "danger")
        return redirect(url_for('job_accounting.list_jobs'))

    # Calculate financial summary
    total_income = db.session.query(func.sum(JobIncome.amount)).filter(
        JobIncome.job_id == job_id,
        JobIncome.status == 'confirmed'
    ).scalar() or Decimal('0.00')

    total_expenses = db.session.query(func.sum(JobExpense.amount)).filter(
        JobExpense.job_id == job_id,
        JobExpense.status == 'confirmed'
    ).scalar() or Decimal('0.00')

    net_profit = total_income - total_expenses
    profit_margin = (net_profit / total_income * 100) if total_income > 0 else Decimal('0.00')

    # Get Purchase Orders linked to this job through expenses
    linked_po_ids = db.session.query(JobExpense.purchase_order_id).filter(
        JobExpense.job_id == job_id,
        JobExpense.purchase_order_id.isnot(None)
    ).distinct().all()
    
    linked_po_ids = [po_id[0] for po_id in linked_po_ids]
    purchase_orders = PurchaseOrder.query.filter(PurchaseOrder.id.in_(linked_po_ids)).all() if linked_po_ids else []

    return render_template(
        'job_accounting/job_view.html',
        job=job,
        total_income=total_income, total_expenses=total_expenses,
        net_profit=net_profit, profit_margin=profit_margin,
        purchase_orders=purchase_orders
    )

@job_accounting_bp.route('/jobs/new')
@login_required
def create_job():
    return "<h1>Create New Job</h1><p>This is a placeholder for the job creation page.</p>"
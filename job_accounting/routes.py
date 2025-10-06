from flask import render_template, request, redirect, url_for, flash, session
from sqlalchemy import or_, func
from decimal import Decimal, InvalidOperation

from app import db
from models import Job, Customer, User, Agency, JobIncome, JobExpense
from . import job_accounting_bp
from auth.utils import login_required, permission_required
from utils.decorators import log_activity


@job_accounting_bp.route('/dashboard')
@login_required
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def dashboard():
    """Render the job accounting dashboard."""
    return render_template('job_accounting/dashboard.html')


@job_accounting_bp.route('/jobs')
@login_required
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def list_jobs(current_agency_id=None):
    user_role = session.get('role')
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
def edit_job(job_id, current_agency_id=None):
    """Edit an existing job."""
    job = Job.query.get_or_404(job_id)
    user_role = session.get('role')

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
def view_job(job_id, current_agency_id=None):
    """View a single job's details."""
    job = Job.query.get_or_404(job_id)
    user_role = session.get('role')

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

    return render_template(
        'job_accounting/job_view.html',
        job=job,
        total_income=total_income, total_expenses=total_expenses,
        net_profit=net_profit, profit_margin=profit_margin
    )

@job_accounting_bp.route('/jobs/new')
@login_required
def create_job():
    return "<h1>Create New Job</h1><p>This is a placeholder for the job creation page.</p>"
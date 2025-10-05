from flask import render_template, request, redirect, url_for, flash, session
from decimal import Decimal, InvalidOperation
from datetime import datetime
from sqlalchemy import func, extract

from app import db
from models import Job, Customer, Agency, User, Location, JobIncome, JobExpense
from . import job_accounting_bp
from auth.utils import login_required, permission_required
from utils.decorators import log_activity


@job_accounting_bp.route("/dashboard")
@login_required
@permission_required(roles=["super_admin", "agency_admin", "agency_manager", "staff"])
def dashboard(current_agency_id=None):
    """Display the job accounting dashboard."""
    user_role = session.get("role")

    base_query = Job.query
    if user_role != "super_admin":
        base_query = base_query.filter_by(agency_id=current_agency_id)

    total_jobs = base_query.count()
    active_jobs = base_query.filter_by(status='active').count()
    completed_jobs = base_query.filter_by(status='completed').count()

    # Financials - Correctly query the underlying tables
    income_query = db.session.query(func.sum(JobIncome.amount)).join(Job).filter(JobIncome.status == 'confirmed')
    expense_query = db.session.query(func.sum(JobExpense.amount)).join(Job).filter(JobExpense.status == 'confirmed')

    if user_role != "super_admin":
        income_query = income_query.filter(Job.agency_id == current_agency_id)
        expense_query = expense_query.filter(Job.agency_id == current_agency_id)

    total_income = income_query.scalar() or Decimal('0.00')
    total_expenses = expense_query.scalar() or Decimal('0.00')
    net_profit = total_income - total_expenses

    # Recent Jobs
    recent_jobs = base_query.order_by(Job.created_at.desc()).limit(5).all()

    # Chart Data
    status_counts = db.session.query(Job.status, func.count(Job.id)).group_by(Job.status).all()

    # Dummy data for charts until real data is available
    monthly_income = []
    monthly_expenses = []

    return render_template(
        "job_accounting/dashboard.html",
        total_jobs=total_jobs,
        active_jobs=active_jobs,
        completed_jobs=completed_jobs,
        net_profit=net_profit,
        total_income=total_income,
        total_expenses=total_expenses,
        recent_jobs=recent_jobs,
        status_counts=status_counts,
        monthly_income=monthly_income,
        monthly_expenses=monthly_expenses
    )


@job_accounting_bp.route("/jobs/create", methods=["GET", "POST"])
@login_required
@permission_required(roles=["super_admin", "agency_admin", "agency_manager"])
@log_activity("create_job")
def create_job(current_agency_id=None):
    """Create a new job."""
    user_role = session.get("role")
    user_id = session.get("user_id")

    if request.method == "POST":
        data = request.form

        # Get job_number from the form instead of auto-generating it
        job_number = data.get("job_number", "").strip()
        job_name = data.get("name", "").strip()
        customer_id = data.get("customer_id")

        if user_role == "super_admin":
            agency_id = data.get("agency_id")
        else:
            agency_id = current_agency_id

        # --- Validation ---
        if not job_number:
            flash("Job Number is required.", "danger")
            return redirect(url_for("job_accounting.create_job"))

        if not job_name:
            flash("Job Name is required.", "danger")
            return redirect(url_for("job_accounting.create_job"))

        if not agency_id:
            flash("Agency is required.", "danger")
            return redirect(url_for("job_accounting.create_job"))

        # Check for unique job number within the agency
        existing_job = Job.query.filter_by(job_number=job_number, agency_id=agency_id).first()
        if existing_job:
            flash(f"Job Number '{job_number}' already exists for this agency.", "danger")
            return redirect(url_for("job_accounting.create_job"))

        try:
            budget_amount = Decimal(data.get("budget_amount") or "0")
            estimated_cost = Decimal(data.get("estimated_cost") or "0")
        except InvalidOperation:
            flash("Invalid budget or cost amount.", "danger")
            return redirect(url_for("job_accounting.create_job"))

        new_job = Job(
            job_number=job_number,
            name=job_name,
            job_type=data.get("job_type"),
            description=data.get("description"),
            customer_id=customer_id if customer_id else None,
            agency_id=agency_id,
            assigned_to=data.get("assigned_to"),
            status=data.get("status", "draft"),
            start_date=datetime.strptime(data.get("start_date"), "%Y-%m-%d").date() if data.get("start_date") else None,
            end_date=datetime.strptime(data.get("end_date"), "%Y-%m-%d").date() if data.get("end_date") else None,
            budget_amount=budget_amount,
            estimated_cost=estimated_cost,
            created_by=user_id,
        )

        db.session.add(new_job)
        db.session.commit()

        flash("Job created successfully!", "success")
        # Assuming a 'view_job' or 'list_jobs' route exists
        return redirect(url_for("job_accounting.list_jobs"))

    # --- For GET request ---
    agencies = []
    customers = []
    users = []

    if user_role == "super_admin":
        agencies = Agency.query.filter_by(is_active=True).all()
        customers = Customer.query.filter_by(is_active=True).all()
        users = User.query.filter_by(is_active=True).all()
    else:
        customers = Customer.query.join(Location).filter(Location.agency_id == current_agency_id, Customer.is_active == True).all()
        users = User.query.filter_by(agency_id=current_agency_id, is_active=True).all()

    # Render the form template from the job_accounting folder
    return render_template(
        "job_accounting/form.html",
        agencies=agencies,
        customers=customers,
        users=users,
        form_type="Create"
    )


@job_accounting_bp.route("/jobs")
@login_required
@permission_required(roles=["super_admin", "agency_admin", "agency_manager", "staff"])
def list_jobs(current_agency_id=None):
    """List all jobs."""
    user_role = session.get("role")
    
    base_query = Job.query
    if user_role != "super_admin":
        base_query = base_query.filter_by(agency_id=current_agency_id)
        
    jobs = base_query.order_by(Job.created_at.desc()).all()
    
    return render_template("job_accounting/list_jobs.html", jobs=jobs)


@job_accounting_bp.route("/jobs/<int:job_id>")
@login_required
@permission_required(roles=["super_admin", "agency_admin", "agency_manager", "staff"])
def view_job(job_id, current_agency_id=None):
    """View a single job's details."""
    user_role = session.get("role")
    
    query = Job.query.filter_by(id=job_id)
    if user_role != "super_admin":
        query = query.filter_by(agency_id=current_agency_id)
        
    job = query.first_or_404()
    
    # You can add pagination for income/expenses later if needed
    income_entries = job.income_entries
    expense_entries = job.expense_entries
    
    return render_template("job_accounting/view_job.html", 
                           job=job, 
                           income_entries=income_entries, 
                           expense_entries=expense_entries)
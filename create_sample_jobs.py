#!/usr/bin/env python3
"""
Sample Data Generator for Job Accounting Module

This script creates sample jobs, income, and expense entries for testing and demonstration.

Usage:
    python create_sample_jobs.py

Requirements:
    - Database tables must be created (run migrate_job_accounting.py first)
    - At least one user, agency, and customer must exist in the database
"""

import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the Flask app
from app import create_app, db
from models import Job, JobIncome, JobExpense, User, Agency, Customer

def create_sample_data():
    """Create sample jobs with income and expense entries."""
    
    print("=" * 60)
    print("Job Accounting Module - Sample Data Generator")
    print("=" * 60)
    print()
    
    app = create_app()
    
    with app.app_context():
        # Check if required data exists
        user = User.query.first()
        if not user:
            print("❌ ERROR: No users found in database.")
            print("   Please create at least one user first.")
            sys.exit(1)
        
        agency = Agency.query.first()
        if not agency:
            print("❌ ERROR: No agencies found in database.")
            print("   Please create at least one agency first.")
            sys.exit(1)
        
        customer = Customer.query.filter_by(agency_id=agency.id).first()
        if not customer:
            print("❌ ERROR: No customers found for this agency.")
            print("   Please create at least one customer first.")
            sys.exit(1)
        
        print(f"✓ Using User: {user.username}")
        print(f"✓ Using Agency: {agency.name}")
        print(f"✓ Using Customer: {customer.name}")
        print()
        
        # Check if sample data already exists
        existing_jobs = Job.query.filter(Job.job_name.like('%Sample%')).count()
        if existing_jobs > 0:
            print(f"⚠️  WARNING: Found {existing_jobs} existing sample jobs.")
            response = input("Do you want to create more sample data? (y/n): ")
            if response.lower() != 'y':
                print("Sample data generation cancelled.")
                sys.exit(0)
            print()
        
        print("Creating sample jobs...")
        print()
        
        # Sample Job 1: Completed Website Project
        job1 = Job(
            job_number=f"JOB{str(Job.query.count() + 1).zfill(5)}",
            name="Sample: Website Redesign Project",
            job_type="client_project",
            description="Complete website redesign with modern UI/UX, responsive design, and SEO optimization.",
            customer_id=customer.id,
            agency_id=agency.id,
            assigned_to=user.id,
            status="completed",
            start_date=datetime.now().date() - timedelta(days=60),
            end_date=datetime.now().date() - timedelta(days=10),
            budget_amount=Decimal("150000.00"),
            estimated_cost=Decimal("100000.00"),
            created_by=user.id
        )
        db.session.add(job1)
        db.session.flush()
        
        # Income for Job 1
        income1_1 = JobIncome(
            job_id=job1.id,
            income_date=datetime.now().date() - timedelta(days=55),
            category="deposit",
            amount=Decimal("50000.00"),
            description="Initial deposit - 30% advance payment",
            payment_method="Bank Transfer",
            reference_number="TXN001234",
            status="confirmed",
            created_by=user.id
        )
        income1_2 = JobIncome(
            job_id=job1.id,
            income_date=datetime.now().date() - timedelta(days=30),
            category="milestone",
            amount=Decimal("50000.00"),
            description="Milestone payment - Design approval",
            payment_method="Bank Transfer",
            reference_number="TXN001567",
            status="confirmed",
            created_by=user.id
        )
        income1_3 = JobIncome(
            job_id=job1.id,
            income_date=datetime.now().date() - timedelta(days=10),
            category="payment",
            amount=Decimal("50000.00"),
            description="Final payment - Project completion",
            payment_method="Bank Transfer",
            reference_number="TXN001890",
            status="confirmed",
            created_by=user.id
        )
        db.session.add_all([income1_1, income1_2, income1_3])
        
        # Expenses for Job 1
        expense1_1 = JobExpense(
            job_id=job1.id,
            expense_date=datetime.now().date() - timedelta(days=50),
            category="labor",
            amount=Decimal("60000.00"),
            description="Developer salaries - 2 developers for 1 month",
            is_billable=False,
            payment_method="Salary Transfer",
            status="confirmed",
            created_by=user.id
        )
        expense1_2 = JobExpense(
            job_id=job1.id,
            expense_date=datetime.now().date() - timedelta(days=45),
            category="software",
            amount=Decimal("5000.00"),
            description="Premium theme and plugins",
            is_billable=True,
            receipt_number="INV-TH-001",
            payment_method="Credit Card",
            status="confirmed",
            created_by=user.id
        )
        expense1_3 = JobExpense(
            job_id=job1.id,
            expense_date=datetime.now().date() - timedelta(days=40),
            category="overhead",
            amount=Decimal("8000.00"),
            description="Hosting, domain, and SSL certificates",
            is_billable=True,
            receipt_number="INV-HOST-001",
            payment_method="Bank Transfer",
            status="confirmed",
            created_by=user.id
        )
        expense1_4 = JobExpense(
            job_id=job1.id,
            expense_date=datetime.now().date() - timedelta(days=35),
            category="marketing",
            amount=Decimal("12000.00"),
            description="Stock photos and graphics",
            is_billable=True,
            receipt_number="INV-STOCK-001",
            payment_method="Credit Card",
            status="confirmed",
            created_by=user.id
        )
        db.session.add_all([expense1_1, expense1_2, expense1_3, expense1_4])
        
        print(f"✓ Created Job 1: {job1.job_name}")
        print(f"  - Income: ₹{job1.total_income or 0:,.2f}")
        print(f"  - Expenses: ₹{job1.total_expenses:,.2f}")
        print(f"  - Profit: ₹{job1.net_profit:,.2f}")
        print()
        
        # Sample Job 2: Active Marketing Campaign
        job2 = Job(
            job_number=f"JOB{str(Job.query.count() + 2).zfill(5)}",
            name="Sample: Digital Marketing Campaign",
            job_type="client_project",
            description="3-month digital marketing campaign including social media, SEO, and content marketing.",
            customer_id=customer.id,
            agency_id=agency.id,
            assigned_to=user.id,
            status="active",
            start_date=datetime.now().date() - timedelta(days=30),
            end_date=datetime.now().date() + timedelta(days=60),
            budget_amount=Decimal("200000.00"),
            estimated_cost=Decimal("150000.00"),
            created_by=user.id
        )
        db.session.add(job2)
        db.session.flush()
        
        # Income for Job 2
        income2_1 = JobIncome(
            job_id=job2.id,
            income_date=datetime.now().date() - timedelta(days=28),
            category="deposit",
            amount=Decimal("80000.00"),
            description="Initial deposit - 40% advance",
            payment_method="Bank Transfer",
            reference_number="TXN002001",
            status="confirmed",
            created_by=user.id
        )
        income2_2 = JobIncome(
            job_id=job2.id,
            income_date=datetime.now().date() + timedelta(days=30),
            category="milestone",
            amount=Decimal("60000.00"),
            description="Month 2 milestone payment",
            payment_method="Bank Transfer",
            status="pending",
            created_by=user.id
        )
        db.session.add_all([income2_1, income2_2])
        
        # Expenses for Job 2
        expense2_1 = JobExpense(
            job_id=job2.id,
            expense_date=datetime.now().date() - timedelta(days=25),
            category="marketing",
            amount=Decimal("30000.00"),
            description="Facebook and Google Ads - Month 1",
            is_billable=False,
            payment_method="Credit Card",
            status="confirmed",
            created_by=user.id
        )
        expense2_2 = JobExpense(
            job_id=job2.id,
            expense_date=datetime.now().date() - timedelta(days=20),
            category="labor",
            amount=Decimal("40000.00"),
            description="Marketing team salaries - Month 1",
            is_billable=False,
            payment_method="Salary Transfer",
            status="confirmed",
            created_by=user.id
        )
        expense2_3 = JobExpense(
            job_id=job2.id,
            expense_date=datetime.now().date() - timedelta(days=15),
            category="software",
            amount=Decimal("8000.00"),
            description="Marketing automation tools subscription",
            is_billable=False,
            payment_method="Credit Card",
            status="confirmed",
            created_by=user.id
        )
        db.session.add_all([expense2_1, expense2_2, expense2_3])
        
        print(f"✓ Created Job 2: {job2.job_name}")
        print(f"  - Income: ₹{job2.total_income or 0:,.2f}")
        print(f"  - Expenses: ₹{job2.total_expenses:,.2f}")
        print(f"  - Profit: ₹{job2.net_profit:,.2f}")
        print()
        
        # Sample Job 3: Internal Project
        job3 = Job(
            job_number=f"JOB{str(Job.query.count() + 3).zfill(5)}",
            name="Sample: Internal CRM Development",
            job_type="internal_project",
            description="Development of internal CRM system for agency operations.",
            customer_id=None,
            agency_id=agency.id,
            assigned_to=user.id,
            status="active",
            start_date=datetime.now().date() - timedelta(days=45),
            end_date=datetime.now().date() + timedelta(days=45),
            budget_amount=Decimal("100000.00"),
            estimated_cost=Decimal("80000.00"),
            created_by=user.id
        )
        db.session.add(job3)
        db.session.flush()
        
        # No income for internal project
        
        # Expenses for Job 3
        expense3_1 = JobExpense(
            job_id=job3.id,
            expense_date=datetime.now().date() - timedelta(days=40),
            category="labor",
            amount=Decimal("50000.00"),
            description="Developer salaries - Month 1",
            is_billable=False,
            payment_method="Salary Transfer",
            status="confirmed",
            created_by=user.id
        )
        expense3_2 = JobExpense(
            job_id=job3.id,
            expense_date=datetime.now().date() - timedelta(days=35),
            category="software",
            amount=Decimal("15000.00"),
            description="Development tools and licenses",
            is_billable=False,
            receipt_number="INV-DEV-001",
            payment_method="Credit Card",
            status="confirmed",
            created_by=user.id
        )
        expense3_3 = JobExpense(
            job_id=job3.id,
            expense_date=datetime.now().date() - timedelta(days=10),
            category="labor",
            amount=Decimal("50000.00"),
            description="Developer salaries - Month 2",
            is_billable=False,
            payment_method="Salary Transfer",
            status="confirmed",
            created_by=user.id
        )
        db.session.add_all([expense3_1, expense3_2, expense3_3])
        
        print(f"✓ Created Job 3: {job3.job_name}")
        print(f"  - Income: ₹{job3.total_income or 0:,.2f}")
        print(f"  - Expenses: ₹{job3.total_expenses:,.2f}")
        print(f"  - Profit: ₹{job3.net_profit:,.2f}")
        print()
        
        # Sample Job 4: Over-Budget Project
        job4 = Job(
            job_number=f"JOB{str(Job.query.count() + 4).zfill(5)}",
            name="Sample: Mobile App Development (Over Budget)",
            job_type="client_project",
            description="Mobile app development project that went over budget due to scope changes.",
            customer_id=customer.id,
            agency_id=agency.id,
            assigned_to=user.id,
            status="review",
            start_date=datetime.now().date() - timedelta(days=90),
            end_date=datetime.now().date() - timedelta(days=5),
            budget_amount=Decimal("120000.00"),
            estimated_cost=Decimal("100000.00"),
            created_by=user.id
        )
        db.session.add(job4)
        db.session.flush()
        
        # Income for Job 4
        income4_1 = JobIncome(
            job_id=job4.id,
            income_date=datetime.now().date() - timedelta(days=85),
            category="deposit",
            amount=Decimal("120000.00"),
            description="Full payment received upfront",
            payment_method="Bank Transfer",
            reference_number="TXN003001",
            status="confirmed",
            created_by=user.id
        )
        db.session.add(income4_1)
        
        # Expenses for Job 4 (over budget)
        expense4_1 = JobExpense(
            job_id=job4.id,
            expense_date=datetime.now().date() - timedelta(days=80),
            category="labor",
            amount=Decimal("80000.00"),
            description="Developer salaries - 2 months",
            is_billable=False,
            payment_method="Salary Transfer",
            status="confirmed",
            created_by=user.id
        )
        expense4_2 = JobExpense(
            job_id=job4.id,
            expense_date=datetime.now().date() - timedelta(days=70),
            category="software",
            amount=Decimal("25000.00"),
            description="Third-party APIs and services",
            is_billable=False,
            receipt_number="INV-API-001",
            payment_method="Credit Card",
            status="confirmed",
            created_by=user.id
        )
        expense4_3 = JobExpense(
            job_id=job4.id,
            expense_date=datetime.now().date() - timedelta(days=60),
            category="equipment",
            amount=Decimal("30000.00"),
            description="Testing devices (iOS and Android)",
            is_billable=False,
            receipt_number="INV-DEV-002",
            payment_method="Credit Card",
            status="confirmed",
            created_by=user.id
        )
        db.session.add_all([expense4_1, expense4_2, expense4_3])
        
        print(f"✓ Created Job 4: {job4.job_name}")
        print(f"  - Income: ₹{job4.total_income or 0:,.2f}")
        print(f"  - Expenses: ₹{job4.total_expenses:,.2f}")
        print(f"  - Profit: ₹{job4.net_profit:,.2f}")
        print(f"  - Budget Variance: ₹{job4.budget_variance:,.2f} (OVER BUDGET)")
        print()
        
        # Commit all changes
        try:
            db.session.commit()
            print("=" * 60)
            print("✅ Sample data created successfully!")
            print("=" * 60)
            print()
            print("Summary:")
            print(f"  - 4 sample jobs created")
            print(f"  - 7 income entries created")
            print(f"  - 13 expense entries created")
            print()
            print("Next steps:")
            print("1. Start your Flask application")
            print("2. Navigate to /job-accounting/dashboard")
            print("3. Explore the sample jobs and their financial data")
            print()
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ ERROR: Failed to create sample data: {str(e)}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    create_sample_data()
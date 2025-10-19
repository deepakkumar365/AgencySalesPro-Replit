from flask import render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import (
    Labour, Contractor, Attendance, LabourAssignment, ContractorAssignment,
    WorkOrder, Agency, User
)
from functools import wraps
from datetime import datetime, timedelta
from decimal import Decimal
from labour_management import labour_management_bp

# Authorization decorators
def require_agency_access(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in ['super_admin', 'agency_admin', 'agency_manager', 'service_manager']:
            flash('Unauthorized access', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== LABOUR MANAGEMENT ====================

# LIST LABOUR
@labour_management_bp.route('/list', methods=['GET'])
@login_required
@require_agency_access
def list_labour():
    """List all labour for agency"""
    is_active = request.args.get('is_active', '1')
    
    if current_user.role == 'super_admin':
        query = Labour.query
    else:
        query = Labour.query.filter_by(agency_id=current_user.agency_id)
    
    if is_active != 'all':
        query = query.filter_by(is_active=is_active == '1')
    
    labour_list = query.all()
    
    return render_template('labour_management/labour_list.html', labour_list=labour_list, is_active=is_active)

# CREATE LABOUR
@labour_management_bp.route('/create', methods=['GET', 'POST'])
@login_required
@require_agency_access
def create_labour():
    """Add new labour/employee"""
    if request.method == 'POST':
        data = request.get_json()
        
        # Verify employee_id uniqueness
        if Labour.query.filter_by(employee_id=data['employee_id']).first():
            return jsonify({'success': False, 'message': 'Employee ID already exists'}), 400
        
        labour = Labour(
            agency_id=current_user.agency_id if current_user.role != 'super_admin' else data['agency_id'],
            name=data['name'],
            employee_id=data['employee_id'],
            role=data.get('role', ''),
            contact_number=data.get('contact_number', ''),
            email=data.get('email', ''),
            wage_rate=Decimal(str(data['wage_rate'])),
            wage_type=data.get('wage_type', 'daily')
        )
        db.session.add(labour)
        db.session.commit()
        
        flash('Labour added successfully', 'success')
        return jsonify({'success': True, 'labour_id': labour.id})
    
    return render_template('labour_management/labour_form.html')

# EDIT LABOUR
@labour_management_bp.route('/<int:labour_id>/edit', methods=['GET', 'POST'])
@login_required
@require_agency_access
def edit_labour(labour_id):
    """Edit labour details"""
    labour = Labour.query.get_or_404(labour_id)
    
    # Verify access
    if current_user.role != 'super_admin' and labour.agency_id != current_user.agency_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('labour_management.list_labour'))
    
    if request.method == 'POST':
        data = request.get_json()
        labour.name = data['name']
        labour.role = data.get('role', '')
        labour.contact_number = data.get('contact_number', '')
        labour.email = data.get('email', '')
        labour.wage_rate = Decimal(str(data['wage_rate']))
        labour.wage_type = data.get('wage_type', 'daily')
        labour.is_active = data.get('is_active', True)
        
        db.session.commit()
        flash('Labour updated successfully', 'success')
        return jsonify({'success': True})
    
    return render_template('labour_management/labour_form.html', labour=labour)

# ==================== ATTENDANCE ====================

# ATTENDANCE DASHBOARD
@labour_management_bp.route('/attendance', methods=['GET'])
@login_required
@require_agency_access
def attendance_dashboard():
    """Labour attendance dashboard"""
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    if current_user.role == 'super_admin':
        labour_list = Labour.query.filter_by(is_active=True).all()
    else:
        labour_list = Labour.query.filter_by(agency_id=current_user.agency_id, is_active=True).all()
    
    attendance_records = Attendance.query.filter_by(attendance_date=date).all()
    attendance_dict = {a.labour_id: a for a in attendance_records}
    
    return render_template(
        'labour_management/attendance_dashboard.html',
        labour_list=labour_list,
        date=date,
        attendance_dict=attendance_dict
    )

# RECORD ATTENDANCE
@labour_management_bp.route('/attendance/record', methods=['POST'])
@login_required
@require_agency_access
def record_attendance():
    """Record attendance for labour"""
    data = request.get_json()
    labour_id = data['labour_id']
    attendance_date = data['attendance_date']
    
    labour = Labour.query.get_or_404(labour_id)
    
    # Verify access
    if current_user.role != 'super_admin' and labour.agency_id != current_user.agency_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    # Check if attendance already exists
    attendance = Attendance.query.filter_by(
        labour_id=labour_id,
        attendance_date=attendance_date
    ).first()
    
    status = data['status']
    hours_worked = Decimal(str(data.get('hours_worked', 0)))
    
    if attendance:
        attendance.status = status
        attendance.hours_worked = hours_worked
        attendance.check_in_time = data.get('check_in_time')
        attendance.check_out_time = data.get('check_out_time')
        attendance.notes = data.get('notes', '')
    else:
        attendance = Attendance(
            labour_id=labour_id,
            attendance_date=attendance_date,
            status=status,
            hours_worked=hours_worked,
            check_in_time=data.get('check_in_time'),
            check_out_time=data.get('check_out_time'),
            notes=data.get('notes', ''),
            recorded_by=current_user.id
        )
        db.session.add(attendance)
    
    db.session.commit()
    flash('Attendance recorded successfully', 'success')
    return jsonify({'success': True, 'attendance_id': attendance.id})

# ATTENDANCE REPORT
@labour_management_bp.route('/attendance/report', methods=['GET'])
@login_required
@require_agency_access
def attendance_report():
    """Labour attendance report"""
    labour_id = request.args.get('labour_id', None)
    from_date = request.args.get('from_date', None)
    to_date = request.args.get('to_date', None)
    
    query = Attendance.query
    
    if labour_id:
        labour = Labour.query.get_or_404(labour_id)
        if current_user.role != 'super_admin' and labour.agency_id != current_user.agency_id:
            flash('Unauthorized access', 'danger')
            return redirect(url_for('labour_management.attendance_dashboard'))
        query = query.filter_by(labour_id=labour_id)
    
    if from_date:
        query = query.filter(Attendance.attendance_date >= from_date)
    if to_date:
        query = query.filter(Attendance.attendance_date <= to_date)
    
    records = query.order_by(Attendance.attendance_date.desc()).all()
    
    return render_template(
        'labour_management/attendance_report.html',
        records=records,
        labour_id=labour_id,
        from_date=from_date,
        to_date=to_date
    )

# ==================== CONTRACTORS ====================

# LIST CONTRACTORS
@labour_management_bp.route('/contractors', methods=['GET'])
@login_required
@require_agency_access
def list_contractors():
    """List all contractors for agency"""
    is_active = request.args.get('is_active', '1')
    
    if current_user.role == 'super_admin':
        query = Contractor.query
    else:
        query = Contractor.query.filter_by(agency_id=current_user.agency_id)
    
    if is_active != 'all':
        query = query.filter_by(is_active=is_active == '1')
    
    contractors = query.all()
    
    return render_template('labour_management/contractors_list.html', contractors=contractors, is_active=is_active)

# CREATE CONTRACTOR
@labour_management_bp.route('/contractors/create', methods=['GET', 'POST'])
@login_required
@require_agency_access
def create_contractor():
    """Add new contractor"""
    if request.method == 'POST':
        data = request.get_json()
        
        contractor = Contractor(
            agency_id=current_user.agency_id if current_user.role != 'super_admin' else data['agency_id'],
            name=data['name'],
            specialty=data.get('specialty', ''),
            contact_number=data.get('contact_number', ''),
            email=data.get('email', ''),
            address=data.get('address', ''),
            payment_terms=data.get('payment_terms', '')
        )
        db.session.add(contractor)
        db.session.commit()
        
        flash('Contractor added successfully', 'success')
        return jsonify({'success': True, 'contractor_id': contractor.id})
    
    return render_template('labour_management/contractor_form.html')

# EDIT CONTRACTOR
@labour_management_bp.route('/contractors/<int:contractor_id>/edit', methods=['GET', 'POST'])
@login_required
@require_agency_access
def edit_contractor(contractor_id):
    """Edit contractor details"""
    contractor = Contractor.query.get_or_404(contractor_id)
    
    # Verify access
    if current_user.role != 'super_admin' and contractor.agency_id != current_user.agency_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('labour_management.list_contractors'))
    
    if request.method == 'POST':
        data = request.get_json()
        contractor.name = data['name']
        contractor.specialty = data.get('specialty', '')
        contractor.contact_number = data.get('contact_number', '')
        contractor.email = data.get('email', '')
        contractor.address = data.get('address', '')
        contractor.payment_terms = data.get('payment_terms', '')
        contractor.is_active = data.get('is_active', True)
        contractor.rating = Decimal(str(data.get('rating', 0)))
        
        db.session.commit()
        flash('Contractor updated successfully', 'success')
        return jsonify({'success': True})
    
    return render_template('labour_management/contractor_form.html', contractor=contractor)

# ==================== ASSIGNMENTS ====================

# ASSIGN LABOUR TO WORK ORDER
@labour_management_bp.route('/assignments/labour/create', methods=['POST'])
@login_required
@require_agency_access
def create_labour_assignment():
    """Assign labour to work order"""
    data = request.get_json()
    
    work_order = WorkOrder.query.get_or_404(data['work_order_id'])
    labour = Labour.query.get_or_404(data['labour_id'])
    
    # Verify access
    if current_user.role != 'super_admin' and work_order.agency_id != current_user.agency_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    # Check for duplicate
    existing = LabourAssignment.query.filter_by(
        work_order_id=data['work_order_id'],
        labour_id=data['labour_id'],
        assignment_date=data['assignment_date']
    ).first()
    
    if existing:
        return jsonify({'success': False, 'message': 'Labour already assigned for this date'}), 400
    
    assignment = LabourAssignment(
        work_order_id=data['work_order_id'],
        labour_id=data['labour_id'],
        hours_worked=Decimal(str(data['hours_worked'])),
        wage_amount=Decimal(str(data.get('wage_amount', 0))),
        assignment_date=data['assignment_date'],
        remarks=data.get('remarks', '')
    )
    db.session.add(assignment)
    db.session.commit()
    
    flash('Labour assigned successfully', 'success')
    return jsonify({'success': True, 'assignment_id': assignment.id})

# ASSIGN CONTRACTOR TO WORK ORDER
@labour_management_bp.route('/assignments/contractor/create', methods=['POST'])
@login_required
@require_agency_access
def create_contractor_assignment():
    """Assign contractor to work order"""
    data = request.get_json()
    
    work_order = WorkOrder.query.get_or_404(data['work_order_id'])
    contractor = Contractor.query.get_or_404(data['contractor_id'])
    
    # Verify access
    if current_user.role != 'super_admin' and work_order.agency_id != current_user.agency_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    # Check for duplicate
    existing = ContractorAssignment.query.filter_by(
        work_order_id=data['work_order_id'],
        contractor_id=data['contractor_id']
    ).first()
    
    if existing:
        return jsonify({'success': False, 'message': 'Contractor already assigned to this work order'}), 400
    
    assignment = ContractorAssignment(
        work_order_id=data['work_order_id'],
        contractor_id=data['contractor_id'],
        agreed_amount=Decimal(str(data['agreed_amount'])),
        assignment_date=data.get('assignment_date', datetime.now().date()),
        remarks=data.get('remarks', '')
    )
    db.session.add(assignment)
    db.session.commit()
    
    flash('Contractor assigned successfully', 'success')
    return jsonify({'success': True, 'assignment_id': assignment.id})

# API: Get labour by agency
@labour_management_bp.route('/api/labour/<int:agency_id>', methods=['GET'])
@login_required
def get_labour_by_agency(agency_id):
    """API endpoint to get labour list for agency"""
    labour_list = Labour.query.filter_by(agency_id=agency_id, is_active=True).all()
    return jsonify([
        {
            'id': l.id,
            'name': l.name,
            'role': l.role,
            'wage_rate': float(l.wage_rate),
            'wage_type': l.wage_type
        }
        for l in labour_list
    ])

# API: Get contractors by agency
@labour_management_bp.route('/api/contractors/<int:agency_id>', methods=['GET'])
@login_required
def get_contractors_by_agency(agency_id):
    """API endpoint to get contractors list for agency"""
    contractors = Contractor.query.filter_by(agency_id=agency_id, is_active=True).all()
    return jsonify([
        {
            'id': c.id,
            'name': c.name,
            'specialty': c.specialty,
            'rating': float(c.rating) if c.rating else 0
        }
        for c in contractors
    ])
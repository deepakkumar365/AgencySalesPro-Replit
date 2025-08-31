from flask import render_template, request, redirect, url_for, flash, session, make_response, jsonify
from werkzeug.utils import secure_filename
import csv, io, os
from app import db
from models import Location, Agency
from location import location_bp
from auth.utils import login_required, role_required, agency_access_required
from utils.decorators import log_activity
import pandas as pd
from datetime import datetime

@location_bp.route('/')
@login_required
@agency_access_required
def list_locations(current_agency_id=None):
    user_role = session.get('role')
    
    if user_role == 'super_admin':
        locations = Location.query.all()
    else:
        locations = Location.query.filter_by(agency_id=current_agency_id).all()
    
    return render_template('location/list.html', locations=locations)

@location_bp.route('/create', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'agency_admin', 'staff')
@log_activity('create_location')
def create_location():
    if request.method == 'POST':
        name = request.form.get('name')
        address = request.form.get('address')
        city = request.form.get('city')
        state = request.form.get('state')
        zip_code = request.form.get('zip_code')
        phone = request.form.get('phone')
        agency_id = request.form.get('agency_id')
        
        user_role = session.get('role')
        current_agency_id = session.get('agency_id')
        
        if not name:
            flash('Location name is required', 'error')
            return render_template('location/form.html', agencies=get_agencies_for_user())
        
        # Non-super admin users can only create locations for their agency
        if user_role != 'super_admin':
            agency_id = current_agency_id
        
        if not agency_id:
            flash('Agency is required', 'error')
            return render_template('location/form.html', agencies=get_agencies_for_user())
        
        location = Location(
            name=name,
            address=address,
            city=city,
            state=state,
            zip_code=zip_code,
            phone=phone,
            agency_id=agency_id,
            is_active=True
        )
        
        db.session.add(location)
        db.session.commit()
        
        flash('Location created successfully!', 'success')
        return redirect(url_for('location.list_locations'))
    
    return render_template('location/form.html', agencies=get_agencies_for_user())

@location_bp.route('/<int:location_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'agency_admin', 'staff')
@log_activity('edit_location')
def edit_location(location_id):
    location = Location.query.get_or_404(location_id)
    
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    
    # Check permissions
    if user_role != 'super_admin' and location.agency_id != current_agency_id:
        flash('You can only edit locations from your agency', 'error')
        return redirect(url_for('location.list_locations'))
    
    if request.method == 'POST':
        location.name = request.form.get('name')
        location.address = request.form.get('address')
        location.city = request.form.get('city')
        location.state = request.form.get('state')
        location.zip_code = request.form.get('zip_code')
        location.phone = request.form.get('phone')
        
        # Super admin can change agency
        if user_role == 'super_admin':
            agency_id = request.form.get('agency_id')
            if agency_id:
                location.agency_id = agency_id
        
        if not location.name:
            flash('Location name is required', 'error')
            return render_template('location/form.html', location=location, agencies=get_agencies_for_user())
        
        db.session.commit()
        flash('Location updated successfully!', 'success')
        return redirect(url_for('location.list_locations'))
    
    return render_template('location/form.html', location=location, agencies=get_agencies_for_user())

@location_bp.route('/<int:location_id>/toggle_status', methods=['POST'])
@login_required
@role_required('super_admin', 'agency_admin')
@log_activity('toggle_location_status')
def toggle_location_status(location_id):
    location = Location.query.get_or_404(location_id)
    
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    
    # Check permissions
    if user_role != 'super_admin' and location.agency_id != current_agency_id:
        flash('You can only modify locations from your agency', 'error')
        return redirect(url_for('location.list_locations'))
    
    location.is_active = not location.is_active
    db.session.commit()
    
    status = 'activated' if location.is_active else 'deactivated'
    flash(f'Location {status} successfully!', 'success')
    return redirect(url_for('location.list_locations'))

@location_bp.route('/<int:location_id>/delete', methods=['POST'])
@login_required
@role_required('super_admin', 'agency_admin')
@log_activity('delete_location')
def delete_location(location_id):
    location = Location.query.get_or_404(location_id)
    
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    
    # Check permissions
    if user_role != 'super_admin' and location.agency_id != current_agency_id:
        flash('You can only delete locations from your agency', 'error')
        return redirect(url_for('location.list_locations'))
    
    # Check if location has customers
    if location.customers:
        flash('Cannot delete location with existing customers', 'error')
        return redirect(url_for('location.list_locations'))
    
    db.session.delete(location)
    db.session.commit()
    
    flash('Location deleted successfully!', 'success')
    return redirect(url_for('location.list_locations'))

def get_agencies_for_user():
    """Get agencies based on current user role"""
    user_role = session.get('role')
    
    if user_role == 'super_admin':
        return Agency.query.filter_by(is_active=True).all()
    else:
        agency_id = session.get('agency_id')
        return Agency.query.filter_by(id=agency_id, is_active=True).all()

# Import/Export Routes

@location_bp.route('/download_template')
@login_required
@role_required('super_admin', 'agency_admin', 'staff')
def download_location_template():
    """Download CSV template for location import"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header row
    writer.writerow(['name', 'address', 'city', 'state', 'zip_code', 'phone', 'agency_code'])
    
    # Write sample data
    writer.writerow(['Sample Location', '123 Main St', 'City Name', 'State', '12345', '555-0123', 'AGENCY001'])
    
    # Create response
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=location_template.csv'
    response.headers['Content-Type'] = 'text/csv'
    
    return response

@location_bp.route('/export')
@login_required
@role_required('super_admin', 'agency_admin', 'staff')
def export_locations():
    """Export existing locations to CSV"""
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    
    # Get locations based on user role
    if user_role == 'super_admin':
        locations = Location.query.join(Agency).all()
    else:
        locations = Location.query.filter_by(agency_id=current_agency_id).join(Agency).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['name', 'address', 'city', 'state', 'zip_code', 'phone', 'agency_code', 'is_active', 'created_at'])
    
    # Write data
    for location in locations:
        writer.writerow([
            location.name,
            location.address or '',
            location.city or '',
            location.state or '',
            location.zip_code or '',
            location.phone or '',
            location.agency.code,
            'Yes' if location.is_active else 'No',
            location.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=locations_export.csv'
    response.headers['Content-Type'] = 'text/csv'
    
    return response

@location_bp.route('/import', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'agency_admin', 'staff')
@log_activity('import_locations')
def import_locations():
    """Import locations from CSV file"""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(url_for('location.import_locations'))
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('location.import_locations'))
        
        if not file.filename.lower().endswith('.csv'):
            flash('Please upload a CSV file', 'error')
            return redirect(url_for('location.import_locations'))
        
        try:
            # Read CSV file
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_input = csv.DictReader(stream)
            
            user_role = session.get('role')
            current_agency_id = session.get('agency_id')
            
            success_count = 0
            error_count = 0
            errors = []
            
            for row_num, row in enumerate(csv_input, start=2):  # Start from 2 to account for header
                try:
                    # Validate required fields
                    if not row.get('name') or not row.get('name').strip():
                        errors.append(f"Row {row_num}: Location name is required")
                        error_count += 1
                        continue
                    
                    agency_code = row.get('agency_code', '').strip()
                    if not agency_code:
                        errors.append(f"Row {row_num}: Agency code is required")
                        error_count += 1
                        continue
                    
                    # Find agency by code
                    agency = Agency.query.filter_by(code=agency_code, is_active=True).first()
                    if not agency:
                        errors.append(f"Row {row_num}: Agency with code '{agency_code}' not found or inactive")
                        error_count += 1
                        continue
                    
                    # Check permissions for non-super admin users
                    if user_role != 'super_admin' and agency.id != current_agency_id:
                        errors.append(f"Row {row_num}: You can only import locations for your agency")
                        error_count += 1
                        continue
                    
                    # Check if location already exists
                    existing_location = Location.query.filter_by(name=row['name'].strip(), agency_id=agency.id).first()
                    if existing_location:
                        errors.append(f"Row {row_num}: Location '{row['name'].strip()}' already exists for this agency")
                        error_count += 1
                        continue
                    
                    # Create new location
                    location = Location(
                        name=row['name'].strip(),
                        address=row.get('address', '').strip(),
                        city=row.get('city', '').strip(),
                        state=row.get('state', '').strip(),
                        zip_code=row.get('zip_code', '').strip(),
                        phone=row.get('phone', '').strip(),
                        agency_id=agency.id,
                        is_active=True
                    )
                    
                    db.session.add(location)
                    success_count += 1
                    
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
                    error_count += 1
            
            if success_count > 0:
                db.session.commit()
                flash(f'Successfully imported {success_count} locations', 'success')
            
            if error_count > 0:
                flash(f'{error_count} errors occurred during import', 'warning')
                # Show first 5 errors
                for error in errors[:5]:
                    flash(error, 'error')
                if len(errors) > 5:
                    flash(f'... and {len(errors) - 5} more errors', 'error')
            
            return redirect(url_for('location.list_locations'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error processing file: {str(e)}', 'error')
            return redirect(url_for('location.import_locations'))
    
    return render_template('location/import.html')

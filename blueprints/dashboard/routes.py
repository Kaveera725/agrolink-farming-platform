from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import db
from models import Crop, Product, Order, User
from datetime import date
from utils.decorators import roles_required

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')


@dashboard_bp.route('/')
@login_required
def index():
    if current_user.role == 'farmer':
        crops = Crop.query.filter_by(farmer_id=current_user.id).order_by(Crop.created_at.desc()).all()
        products = Product.query.filter_by(farmer_id=current_user.id).order_by(Product.created_at.desc()).all()
        orders_received = Order.query.join(Product).filter(
            Product.farmer_id == current_user.id
        ).order_by(Order.created_at.desc()).limit(5).all()
        total_revenue = sum(
            o.total_price for o in Order.query.join(Product)
            .filter(Product.farmer_id == current_user.id, Order.status != 'cancelled').all()
        )
        return render_template('dashboard/farmer.html',
                               crops=crops, products=products,
                               orders=orders_received, total_revenue=total_revenue)
    else:
        orders = Order.query.filter_by(buyer_id=current_user.id).order_by(Order.created_at.desc()).all()
        total_spent = sum(o.total_price for o in orders if o.status != 'cancelled')
        return render_template('dashboard/buyer.html', orders=orders, total_spent=total_spent)


# ── CROP MANAGEMENT ──────────────────────────────────────────────────────────

@dashboard_bp.route('/crops')
@roles_required('farmer')
def crops():
    crops = Crop.query.filter_by(farmer_id=current_user.id).order_by(Crop.created_at.desc()).all()
    return render_template('dashboard/crops.html', crops=crops)


@dashboard_bp.route('/crops/add', methods=['GET', 'POST'])
@roles_required('farmer')
def add_crop():
    if request.method == 'POST':
        crop_name = request.form.get('crop_name', '').strip()
        crop_type = request.form.get('crop_type', '').strip()
        quantity_kg = request.form.get('quantity_kg', 0)
        harvest_date = request.form.get('expected_harvest_date', '')
        field_location = request.form.get('field_location', '').strip()
        notes = request.form.get('notes', '').strip()
        status = request.form.get('status', 'growing')

        if not crop_name or not crop_type or not harvest_date:
            flash('Crop name, type and harvest date are required.', 'error')
            return render_template('dashboard/crop_form.html', action='Add')
        try:
            harvest_date = date.fromisoformat(harvest_date)
            quantity_kg = float(quantity_kg)
        except (ValueError, TypeError):
            flash('Invalid date or quantity.', 'error')
            return render_template('dashboard/crop_form.html', action='Add')

        crop = Crop(farmer_id=current_user.id, crop_name=crop_name, crop_type=crop_type,
                    quantity_kg=quantity_kg, expected_harvest_date=harvest_date,
                    field_location=field_location, notes=notes, status=status)
        db.session.add(crop)
        db.session.commit()
        flash('Crop added successfully!', 'success')
        return redirect(url_for('dashboard.crops'))
    return render_template('dashboard/crop_form.html', action='Add', crop=None)


@dashboard_bp.route('/crops/<int:crop_id>/edit', methods=['GET', 'POST'])
@roles_required('farmer')
def edit_crop(crop_id):
    crop = Crop.query.filter_by(id=crop_id, farmer_id=current_user.id).first_or_404()
    if request.method == 'POST':
        crop.crop_name = request.form.get('crop_name', crop.crop_name).strip()
        crop.crop_type = request.form.get('crop_type', crop.crop_type).strip()
        crop.field_location = request.form.get('field_location', '').strip()
        crop.notes = request.form.get('notes', '').strip()
        crop.status = request.form.get('status', crop.status)
        try:
            crop.quantity_kg = float(request.form.get('quantity_kg', crop.quantity_kg))
            crop.expected_harvest_date = date.fromisoformat(request.form.get('expected_harvest_date'))
        except (ValueError, TypeError):
            flash('Invalid date or quantity.', 'error')
            return render_template('dashboard/crop_form.html', action='Edit', crop=crop)
        db.session.commit()
        flash('Crop updated successfully!', 'success')
        return redirect(url_for('dashboard.crops'))
    return render_template('dashboard/crop_form.html', action='Edit', crop=crop)


@dashboard_bp.route('/crops/<int:crop_id>/delete', methods=['POST'])
@roles_required('farmer')
def delete_crop(crop_id):
    crop = Crop.query.filter_by(id=crop_id, farmer_id=current_user.id).first_or_404()
    db.session.delete(crop)
    db.session.commit()
    flash('Crop deleted.', 'info')
    return redirect(url_for('dashboard.crops'))
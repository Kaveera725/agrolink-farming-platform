from functools import wraps
from flask import flash, redirect, url_for, request
from flask_login import current_user, logout_user


def roles_required(*roles):
    """
    Decorator requiring the logged-in user to have at least one of the specified roles.
    Also ensures the user is active (not deactivated).

    Usage:
        @roles_required('farmer')
        @roles_required('admin')
        @roles_required('farmer', 'buyer')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json or request.path.endswith('/quote'):
                    return {'error': 'Authentication required.'}, 401
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login', next=request.path))

            if not getattr(current_user, 'is_active', True):
                logout_user()
                if request.is_json or request.path.endswith('/quote'):
                    return {'error': 'Your account has been deactivated.'}, 403
                flash('Your account has been deactivated. Please contact support.', 'error')
                return redirect(url_for('auth.login'))

            if current_user.role not in roles:
                if request.is_json or request.path.endswith('/quote'):
                    return {'error': 'Access denied. You do not have permission to access this resource.'}, 403
                flash('Access denied. You do not have permission to access this page.', 'error')
                return redirect(url_for('dashboard.index'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator

"""
AgroLink Design System Styleguide
─────────────────────────────────
Dev-only route: /_styleguide
Only registered when app.debug == True.

Shows every design token and component in all states for visual QA.
"""
from flask import Blueprint, render_template, current_app, abort

styleguide_bp = Blueprint('styleguide', __name__, url_prefix='/_styleguide')


@styleguide_bp.before_request
def dev_only():
    """Block access in production."""
    if not current_app.debug:
        abort(404)


@styleguide_bp.route('/')
def index():
    return render_template('styleguide/index.html')

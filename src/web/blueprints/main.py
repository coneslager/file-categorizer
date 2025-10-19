"""Main web interface blueprint."""

from flask import Blueprint, render_template

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Main dashboard page."""
    return render_template('index.html')


@main_bp.route('/search')
def search():
    """Search interface page."""
    return render_template('search.html')


@main_bp.route('/scan')
def scan():
    """Scan interface page."""
    return render_template('scan.html')


@main_bp.route('/cleanup')
def cleanup():
    """Cleanup interface page."""
    return render_template('cleanup.html')
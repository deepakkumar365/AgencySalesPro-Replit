from flask import Blueprint

# Agency Manager blueprint
agency_manager_bp = Blueprint('agency_manager', __name__, template_folder='templates')

# Import routes after blueprint to avoid circular imports
from . import routes  # noqa: E402,F401
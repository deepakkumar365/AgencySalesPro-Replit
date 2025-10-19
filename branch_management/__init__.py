from flask import Blueprint

branch_management_bp = Blueprint('branch_management', __name__, url_prefix='/branches')

from . import routes
from flask import Blueprint

garage_billing_bp = Blueprint('garage_billing', __name__, url_prefix='/garage-billing')

from . import routes
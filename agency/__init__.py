from flask import Blueprint

agency_bp = Blueprint('agency', __name__)

from . import routes

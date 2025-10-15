from flask import Blueprint

forecasting_bp = Blueprint('forecasting', __name__)

from forecasting import routes
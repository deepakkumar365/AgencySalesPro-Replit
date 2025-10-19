from flask import Blueprint

garage_expenses_bp = Blueprint('garage_expenses', __name__, url_prefix='/expenses')

from . import routes
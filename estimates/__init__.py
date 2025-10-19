from flask import Blueprint

estimates_bp = Blueprint('estimates', __name__, url_prefix='/estimates')

from . import routes
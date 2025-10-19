from flask import Blueprint

labour_management_bp = Blueprint('labour_management', __name__, url_prefix='/labour')

from . import routes
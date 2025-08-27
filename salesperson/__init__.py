from flask import Blueprint

salesperson_bp = Blueprint('salesperson', __name__)

from . import routes

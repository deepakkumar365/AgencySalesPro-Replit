from flask import Blueprint

product_bp = Blueprint('product', __name__)

from . import routes

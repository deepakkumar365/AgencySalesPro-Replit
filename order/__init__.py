from flask import Blueprint

order_bp = Blueprint('order', __name__)

from . import routes

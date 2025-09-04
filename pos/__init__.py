from flask import Blueprint

pos_bp = Blueprint('pos', __name__, url_prefix='/pos')

from pos import routes
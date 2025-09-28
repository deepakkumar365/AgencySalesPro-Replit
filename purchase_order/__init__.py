from flask import Blueprint

purchase_order_bp = Blueprint("purchase_order", __name__, template_folder="../templates/purchase_order")

from . import routes  # noqa: E402, F401
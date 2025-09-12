from flask import Blueprint

# Define blueprint for product overrides
overrides_bp = Blueprint('product_overrides', __name__, url_prefix='/product-overrides')

# Import routes so their decorators register with the blueprint
from . import routes  # noqa: E402,F401
from flask import Blueprint

# Define the blueprint for the service module
service_bp = Blueprint('service', __name__, template_folder='templates', static_folder='static')

from . import routes
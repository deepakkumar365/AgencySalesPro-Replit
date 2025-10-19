"""
Service module - handles service-centric operations for service agencies.
Includes work orders, vehicles, service catalog, and technician management.
"""

from flask import Blueprint

service_bp = Blueprint(
    'service',
    __name__,
    template_folder='templates',
    url_prefix='/service'
)

from . import routes
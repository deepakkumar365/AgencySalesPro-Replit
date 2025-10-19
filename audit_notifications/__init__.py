from flask import Blueprint

audit_notifications_bp = Blueprint('audit_notifications', __name__, url_prefix='/audit-notifications')

from . import routes
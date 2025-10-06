from flask import Blueprint

job_accounting_bp = Blueprint("job_accounting", __name__, template_folder="../templates")

from . import routes
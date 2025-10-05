from flask import Blueprint

job_accounting_bp = Blueprint("job_accounting", __name__, url_prefix="/job-accounting", template_folder="../templates/job_accounting")
 
from . import routes # noqa: F401, E402
def apply_pagination(query, page_param='page', per_page=10, per_page_param='per_page'):
    """Apply Flask-SQLAlchemy pagination to a query.
    Returns a Pagination object.
    """
    from flask import request
    page = request.args.get(page_param, 1, type=int)
    per = request.args.get(per_page_param, per_page, type=int)
    # enforce allowed per_page values
    if per not in [10, 20, 50, 100]:
        per = per_page
    return query.paginate(page=page, per_page=per, error_out=False)

from main import app
from flask import url_for

with app.test_request_context():
    try:
        url = url_for('pos.dashboard_mobile')
        print(f"URL for pos.dashboard_mobile: {url}")
    except Exception as e:
        print(f"Error generating URL: {e}")

    print("Registered Routes:")
    for rule in app.url_map.iter_rules():
        if 'pos' in rule.endpoint:
            print(f"{rule.endpoint}: {rule}")

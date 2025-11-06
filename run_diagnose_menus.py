'''
Run the menu diagnosis script.
'''
from app import create_app
from diagnose_menus import diagnose_menus

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        diagnose_menus()

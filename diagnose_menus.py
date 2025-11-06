import os
import logging
from app import create_app, db
from models import Role
from service.menu_service import MenuService

# Configure logging
logging.basicConfig(level=logging.INFO)

def diagnose_menus():
    '''Diagnose menu loading for all roles'''
    try:
        # Get all roles
        roles = Role.query.order_by(Role.name).all()
        if not roles:
            logging.warning("No roles found in the database.")
            return

        logging.info(f"Found {len(roles)} roles. Diagnosing menus for each...")

        for role in roles:
            logging.info(f"--- Role: {role.name} (ID: {role.id}) ---")
            
            # Invalidate cache to ensure fresh data
            MenuService.invalidate_cache(role.id)
            
            # Get menus using the service
            menus = MenuService.get_menus_by_role(role.id)
            
            if not menus:
                logging.warning(f"No menus found for role: {role.name}")
            else:
                logging.info(f"Found {len(menus)} parent menus for role: {role.name}")
                for parent in menus:
                    logging.info(f"  - {parent['display_name']} (URL: {parent['url']})")
                    if parent['children']:
                        for child in parent['children']:
                            logging.info(f"    - {child['display_name']} (URL: {child['url']})")
        
        logging.info("--- Diagnosis Complete ---")

    except Exception as e:
        logging.exception(f"An error occurred during menu diagnosis: {e}")

app = create_app()

@app.cli.command('diagnose-menus')
def diagnose_menus_command():
    """Diagnose menu loading for all roles"""
    diagnose_menus()

if __name__ == "__main__":
    with app.app_context():
        diagnose_menus()

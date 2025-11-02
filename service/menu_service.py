"""
Menu Service: Handles menu retrieval, caching, and role-based filtering
"""
from extensions import db, cache
from models import MenuItem, MenuRole, Role
from sqlalchemy import and_


class MenuService:
    """Service for managing menus and role-based access"""

    CACHE_KEY_PREFIX = "menu_role_"
    CACHE_TIMEOUT = 3600  # 1 hour

    @staticmethod
    def get_menus_by_role(role_id: int, include_inactive: bool = False):
        """
        Get all menus accessible by a specific role, organized hierarchically.
        
        Args:
            role_id: ID of the role
            include_inactive: Include inactive menus (default: False)
        
        Returns:
            List of menu items with children, sorted by order_index
        """
        cache_key = f"{MenuService.CACHE_KEY_PREFIX}{role_id}"
        
        # Try to get from cache
        cached_menus = cache.get(cache_key)
        if cached_menus is not None:
            return cached_menus
        
        # Build menus from database
        menus = MenuService._build_menu_tree(role_id, include_inactive)
        
        # Cache the result
        cache.set(cache_key, menus, timeout=MenuService.CACHE_TIMEOUT)
        
        return menus

    @staticmethod
    def _build_menu_tree(role_id: int, include_inactive: bool = False):
        """
        Build hierarchical menu structure from database.
        
        Returns parent menus with children, sorted by order_index.
        """
        # Get all menu IDs accessible by this role
        query = db.session.query(MenuRole.menu_id).filter(
            MenuRole.role_id == role_id
        )
        
        menu_ids = [row[0] for row in query.all()]
        
        if not menu_ids:
            return []
        
        # Build filter conditions
        conditions = [MenuItem.id.in_(menu_ids)]
        if not include_inactive:
            conditions.append(MenuItem.is_active == True)
        
        # Get all accessible menu items
        menu_items = MenuItem.query.filter(and_(*conditions)).all()
        
        # Build dictionary for quick lookup
        menu_dict = {m.id: m for m in menu_items}
        
        # Get parent menus (where parent_id is None or parent is not in accessible menus)
        parent_menus = [
            m for m in menu_items 
            if m.parent_id is None or m.parent_id not in menu_dict
        ]
        
        # Sort parents by order_index
        parent_menus.sort(key=lambda x: x.order_index)
        
        # Build result with children
        result = []
        for parent in parent_menus:
            menu_dict_result = {
                'id': parent.id,
                'name': parent.name,
                'display_name': parent.display_name,
                'url': parent.url,
                'icon': parent.icon,
                'order_index': parent.order_index,
                'is_active': parent.is_active,
                'children': []
            }
            
            # Get children and sort them
            if parent.id in menu_dict:
                children = [
                    m for m in menu_items 
                    if m.parent_id == parent.id
                ]
                children.sort(key=lambda x: x.order_index)
                
                menu_dict_result['children'] = [
                    {
                        'id': child.id,
                        'name': child.name,
                        'display_name': child.display_name,
                        'url': child.url,
                        'icon': child.icon,
                        'order_index': child.order_index,
                        'is_active': child.is_active,
                    }
                    for child in children
                ]
            
            result.append(menu_dict_result)
        
        return result

    @staticmethod
    def get_menus_by_role_name(role_name: str, include_inactive: bool = False):
        """
        Get menus by role name instead of role ID.
        
        Args:
            role_name: Name of the role (e.g., 'super_admin', 'agency_admin')
            include_inactive: Include inactive menus (default: False)
        
        Returns:
            List of menu items with children
        """
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            return []
        
        return MenuService.get_menus_by_role(role.id, include_inactive)

    @staticmethod
    def invalidate_cache(role_id: int = None):
        """
        Invalidate menu cache for a specific role or all roles.
        
        Args:
            role_id: ID of the role to invalidate cache for. If None, invalidates all role caches.
        """
        if role_id is not None:
            cache_key = f"{MenuService.CACHE_KEY_PREFIX}{role_id}"
            cache.delete(cache_key)
        else:
            # Invalidate all menu caches by clearing keys with the prefix
            # This is a simplified approach; for Redis, you'd use scan_iter
            cache.clear()

    @staticmethod
    def add_menu_to_role(menu_id: int, role_id: int):
        """
        Assign a menu to a role.
        
        Args:
            menu_id: ID of the menu item
            role_id: ID of the role
        
        Returns:
            MenuRole object or None if already exists
        """
        # Check if already exists
        existing = MenuRole.query.filter(
            and_(
                MenuRole.menu_id == menu_id,
                MenuRole.role_id == role_id
            )
        ).first()
        
        if existing:
            return None
        
        # Create new mapping
        menu_role = MenuRole(menu_id=menu_id, role_id=role_id)
        db.session.add(menu_role)
        db.session.commit()
        
        # Invalidate cache
        MenuService.invalidate_cache(role_id)
        
        return menu_role

    @staticmethod
    def remove_menu_from_role(menu_id: int, role_id: int):
        """
        Remove a menu from a role.
        
        Args:
            menu_id: ID of the menu item
            role_id: ID of the role
        
        Returns:
            True if removed, False if not found
        """
        menu_role = MenuRole.query.filter(
            and_(
                MenuRole.menu_id == menu_id,
                MenuRole.role_id == role_id
            )
        ).first()
        
        if not menu_role:
            return False
        
        db.session.delete(menu_role)
        db.session.commit()
        
        # Invalidate cache
        MenuService.invalidate_cache(role_id)
        
        return True

    @staticmethod
    def get_all_menus():
        """
        Get all menus (admin purposes).
        
        Returns:
            List of all menu items organized hierarchically
        """
        # Get all active parent menus
        parent_menus = MenuItem.query.filter(
            and_(
                MenuItem.parent_id == None,
                MenuItem.is_active == True
            )
        ).order_by(MenuItem.order_index).all()
        
        result = []
        for parent in parent_menus:
            menu_dict = {
                'id': parent.id,
                'name': parent.name,
                'display_name': parent.display_name,
                'url': parent.url,
                'icon': parent.icon,
                'order_index': parent.order_index,
                'is_active': parent.is_active,
                'children': []
            }
            
            # Get children
            children = MenuItem.query.filter(
                and_(
                    MenuItem.parent_id == parent.id,
                    MenuItem.is_active == True
                )
            ).order_by(MenuItem.order_index).all()
            
            menu_dict['children'] = [
                {
                    'id': child.id,
                    'name': child.name,
                    'display_name': child.display_name,
                    'url': child.url,
                    'icon': child.icon,
                    'order_index': child.order_index,
                    'is_active': child.is_active,
                }
                for child in children
            ]
            
            result.append(menu_dict)
        
        return result

    @staticmethod
    def get_role_menus(role_id: int):
        """
        Get menu IDs currently assigned to a role.
        
        Returns:
            List of menu IDs
        """
        menu_ids = db.session.query(MenuRole.menu_id).filter(
            MenuRole.role_id == role_id
        ).all()
        
        return [row[0] for row in menu_ids]
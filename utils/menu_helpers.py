"""
Menu helper functions for role-based navigation rendering.
Generates menu structures based on user role and permissions.
"""

def get_service_menu_items(user_role):
    """
    Generate service menu items based on user role.
    Implements the service-centric menu structure from service_centric_plan.md
    """
    
    menu_structure = {
        'service_manager': {
            'label': 'Service Operations',
            'icon': 'fas fa-tools',
            'items': [
                {
                    'label': 'Service Dashboard',
                    'url': 'service.dashboard',
                    'icon': 'fas fa-tachometer-alt',
                    'divider_before': False
                },
                {
                    'label': 'Work Orders',
                    'icon': 'fas fa-file-alt',
                    'submenu': [
                        {'label': 'All Work Orders', 'url': 'service.list_work_orders', 'icon': 'fas fa-list'},
                        {'label': 'New Work Order', 'url': 'service.create_work_order', 'icon': 'fas fa-plus-circle'},
                        {'label': 'In Progress', 'url': 'service.list_work_orders', 'params': {'status': 'In Progress'}, 'icon': 'fas fa-spinner'},
                        {'label': 'Completed', 'url': 'service.list_work_orders', 'params': {'status': 'Completed'}, 'icon': 'fas fa-check-circle'},
                        {'label': 'Pending Approvals', 'url': 'service.list_work_orders', 'params': {'status': 'Estimate'}, 'icon': 'fas fa-hourglass-start'},
                    ]
                },
                # Vehicles removed from UI (vehicle management disabled)
                {
                    'label': 'Technicians',
                    'icon': 'fas fa-user-tie',
                    'submenu': [
                        {'label': 'Technician Workload', 'url': 'service.list_technicians', 'icon': 'fas fa-tasks'},
                        {'label': 'Assign Tasks', 'url': 'service.assign_tasks', 'icon': 'fas fa-clipboard-list'},
                        {'label': 'Productivity View', 'url': 'service.technician_productivity', 'icon': 'fas fa-chart-bar'},
                    ],
                    'divider_before': True
                },
                {
                    'label': 'Service Catalog',
                    'icon': 'fas fa-wrench',
                    'submenu': [
                        {'label': 'Services List', 'url': 'service.list_services', 'icon': 'fas fa-list'},
                        {'label': 'Add/Edit Service', 'url': 'service.create_service', 'icon': 'fas fa-plus-circle'},
                    ],
                    'divider_before': True
                },
                {
                    'label': 'Inventory',
                    'icon': 'fas fa-boxes',
                    'submenu': [
                        {'label': 'Stock Levels', 'url': 'inventory.stock_levels', 'icon': 'fas fa-layer-group'},
                        {'label': 'Adjust Stock', 'url': 'inventory.adjust_stock', 'icon': 'fas fa-edit'},
                    ]
                },
                {
                    'label': 'Labor Management',
                    'icon': 'fas fa-clock',
                    'submenu': [
                        {'label': 'Technician Rates', 'url': 'service.technician_rates', 'icon': 'fas fa-dollar-sign'},
                        {'label': 'Labor Costs', 'url': 'service.labor_costs', 'icon': 'fas fa-chart-line'},
                    ]
                },
                {
                    'label': 'Reports',
                    'icon': 'fas fa-chart-bar',
                    'submenu': [
                        {'label': 'Service Revenue', 'url': 'service.revenue_report', 'icon': 'fas fa-dollar-sign'},
                        {'label': 'Job Profitability', 'url': 'service.profitability_report', 'icon': 'fas fa-chart-line'},
                        {'label': 'Technician Productivity', 'url': 'service.productivity_report', 'icon': 'fas fa-chart-bar'},
                        {'label': 'Inventory Valuation', 'url': 'service.inventory_valuation', 'icon': 'fas fa-boxes'},
                        {'label': 'Customer Aging', 'url': 'service.customer_aging', 'icon': 'fas fa-calendar'},
                    ],
                    'divider_before': True
                },
                {
                    'label': 'Settings',
                    'icon': 'fas fa-cog',
                    'submenu': [
                        {'label': 'Agency Settings', 'url': 'service.settings', 'icon': 'fas fa-cog'},
                        {'label': 'User Management', 'url': 'service.users', 'icon': 'fas fa-users'},
                        {'label': 'Role Permissions', 'url': 'service.permissions', 'icon': 'fas fa-lock'},
                    ],
                    'divider_before': True
                },
            ]
        },
        'service_advisor': {
            'label': 'Service Operations',
            'icon': 'fas fa-tools',
            'items': [
                {
                    'label': 'Service Dashboard',
                    'url': 'service.dashboard',
                    'icon': 'fas fa-tachometer-alt',
                    'divider_before': False
                },
                {
                    'label': 'Work Orders',
                    'icon': 'fas fa-file-alt',
                    'submenu': [
                        {'label': 'My Work Orders', 'url': 'service.list_work_orders', 'params': {'filter': 'my'}, 'icon': 'fas fa-list'},
                        {'label': 'Create New Work Order', 'url': 'service.create_work_order', 'icon': 'fas fa-plus-circle'},
                        {'label': 'Pending Approvals', 'url': 'service.list_work_orders', 'params': {'status': 'Estimate'}, 'icon': 'fas fa-hourglass-start'},
                        {'label': 'Completed', 'url': 'service.list_work_orders', 'params': {'status': 'Completed'}, 'icon': 'fas fa-check-circle'},
                    ]
                },
                # Vehicles removed from UI (vehicle management disabled)
                {
                    'label': 'Customer Info',
                    'icon': 'fas fa-user-friends',
                    'submenu': [
                        {'label': 'Customer Directory', 'url': 'customer.list_customers', 'icon': 'fas fa-address-book'},
                        {'label': 'Contact Management', 'url': 'service.manage_contacts', 'icon': 'fas fa-phone'},
                    ],
                    'divider_before': True
                },
                {
                    'label': 'Service Catalog',
                    'url': 'service.list_services',
                    'icon': 'fas fa-wrench',
                    'note': '(view only)'
                },
                {
                    'label': 'Inventory',
                    'icon': 'fas fa-boxes',
                    'submenu': [
                        {'label': 'Stock Levels', 'url': 'inventory.stock_levels', 'icon': 'fas fa-layer-group', 'note': '(view only)'},
                        {'label': 'Quick Part Lookup', 'url': 'service.parts_lookup', 'icon': 'fas fa-search'},
                    ],
                    'divider_before': True
                },
                {
                    'label': 'Reports',
                    'icon': 'fas fa-chart-bar',
                    'submenu': [
                        {'label': 'My Work Orders Revenue', 'url': 'service.my_revenue_report', 'icon': 'fas fa-dollar-sign'},
                        {'label': 'Customer Aging', 'url': 'service.customer_aging', 'icon': 'fas fa-calendar'},
                    ],
                    'divider_before': True
                },
            ]
        },
        'technician': {
            'label': 'My Workload',
            'icon': 'fas fa-tasks',
            'items': [
                {
                    'label': 'My Workload Dashboard',
                    'url': 'service.my_workload',
                    'icon': 'fas fa-tachometer-alt',
                    'divider_before': False
                },
                {
                    'label': 'My Work Orders',
                    'icon': 'fas fa-file-alt',
                    'submenu': [
                        {'label': 'Ready to Start', 'url': 'service.my_work_orders', 'params': {'status': 'Approved'}, 'icon': 'fas fa-hourglass-start'},
                        {'label': 'In Progress', 'url': 'service.my_work_orders', 'params': {'status': 'In Progress'}, 'icon': 'fas fa-spinner'},
                        {'label': 'Completed', 'url': 'service.my_work_orders', 'params': {'status': 'Completed'}, 'icon': 'fas fa-check-circle'},
                    ]
                },
                {
                    'label': 'Update Status',
                    'icon': 'fas fa-edit',
                    'submenu': [
                        {'label': 'Start Work Order', 'url': 'service.start_work', 'icon': 'fas fa-play'},
                        {'label': 'Record Time', 'url': 'service.record_time', 'icon': 'fas fa-clock'},
                        {'label': 'Record Parts Used', 'url': 'service.record_parts', 'icon': 'fas fa-boxes'},
                        {'label': 'Mark Complete', 'url': 'service.complete_work', 'icon': 'fas fa-check-circle'},
                    ],
                    'divider_before': True
                },
                {
                    'label': 'Inventory (Limited)',
                    'icon': 'fas fa-boxes',
                    'submenu': [
                        {'label': 'Parts for My WOs', 'url': 'service.my_parts', 'icon': 'fas fa-list'},
                        {'label': 'Record Usage', 'url': 'service.record_parts', 'icon': 'fas fa-edit'},
                    ],
                    'divider_before': True
                },
                {
                    'label': 'My Performance',
                    'url': 'service.my_performance',
                    'icon': 'fas fa-chart-bar',
                    'divider_before': True
                },
                {
                    'label': 'My Schedule',
                    'url': 'service.my_schedule',
                    'icon': 'fas fa-calendar'
                },
                {
                    'label': 'My Time Entries',
                    'url': 'service.my_time_entries',
                    'icon': 'fas fa-clock'
                },
            ]
        },
        'store_manager': {
            'label': 'Inventory Management',
            'icon': 'fas fa-boxes',
            'items': [
                {
                    'label': 'Inventory Dashboard',
                    'url': 'inventory.dashboard',
                    'icon': 'fas fa-tachometer-alt',
                    'divider_before': False
                },
                {
                    'label': 'Stock Levels',
                    'url': 'inventory.stock_levels',
                    'icon': 'fas fa-layer-group'
                },
                {
                    'label': 'Adjust Stock',
                    'icon': 'fas fa-edit',
                    'submenu': [
                        {'label': 'Manual Adjustment', 'url': 'inventory.adjust_stock', 'icon': 'fas fa-edit'},
                        {'label': 'Bulk Adjustments', 'url': 'inventory.bulk_adjust', 'icon': 'fas fa-list'},
                    ]
                },
                {
                    'label': 'Stock Transfers',
                    'url': 'inventory.transfers',
                    'icon': 'fas fa-exchange-alt'
                },
                {
                    'label': 'Low Stock Alerts',
                    'url': 'inventory.low_stock_alerts',
                    'icon': 'fas fa-exclamation-triangle'
                },
                {
                    'label': 'Suppliers',
                    'icon': 'fas fa-truck',
                    'submenu': [
                        {'label': 'Supplier List', 'url': 'inventory.list_suppliers', 'icon': 'fas fa-list'},
                        {'label': 'Add Supplier', 'url': 'inventory.add_supplier', 'icon': 'fas fa-plus-circle'},
                    ],
                    'divider_before': True
                },
                {
                    'label': 'Inventory Operations',
                    'icon': 'fas fa-cogs',
                    'submenu': [
                        {'label': 'Receive Inventory', 'url': 'inventory.receive', 'icon': 'fas fa-arrow-down'},
                        {'label': 'Return Items', 'url': 'inventory.return_items', 'icon': 'fas fa-arrow-up'},
                        {'label': 'Inventory Audits', 'url': 'inventory.audits', 'icon': 'fas fa-list-check'},
                    ],
                    'divider_before': True
                },
                {
                    'label': 'Reports',
                    'icon': 'fas fa-chart-bar',
                    'submenu': [
                        {'label': 'Stock Valuation', 'url': 'inventory.valuation_report', 'icon': 'fas fa-dollar-sign'},
                        {'label': 'Usage by Work Order', 'url': 'inventory.usage_report', 'icon': 'fas fa-chart-line'},
                        {'label': 'Supplier Performance', 'url': 'inventory.supplier_report', 'icon': 'fas fa-chart-bar'},
                        {'label': 'Inventory Transactions', 'url': 'inventory.transactions', 'icon': 'fas fa-history'},
                    ],
                    'divider_before': True
                },
                {
                    'label': 'Settings',
                    'icon': 'fas fa-cog',
                    'submenu': [
                        {'label': 'Service Catalog', 'url': 'service.list_services', 'icon': 'fas fa-wrench', 'note': '(view parts only)'},
                        {'label': 'Inventory Settings', 'url': 'inventory.settings', 'icon': 'fas fa-cog'},
                    ],
                    'divider_before': True
                },
            ]
        }
    }
    
    return menu_structure.get(user_role, {})


def render_menu_item(item, url_for_func):
    """
    Helper to render a single menu item with its submenu if applicable.
    Returns dict with rendering information.
    """
    result = {
        'label': item.get('label'),
        'icon': item.get('icon', 'fas fa-link'),
        'has_submenu': 'submenu' in item,
        'divider_before': item.get('divider_before', False),
        'note': item.get('note', '')
    }
    
    if 'url' in item:
        params = item.get('params', {})
        try:
            result['url'] = url_for_func(item['url'], **params)
        except:
            result['url'] = '#'
    
    if 'submenu' in item:
        result['submenu'] = [
            render_menu_item(subitem, url_for_func) for subitem in item['submenu']
        ]
    
    return result


def get_all_service_roles():
    """Return list of all service-related roles."""
    return ['service_manager', 'service_advisor', 'technician', 'store_manager']


def is_service_role(user_role):
    """Check if user has a service-related role."""
    return user_role in get_all_service_roles()
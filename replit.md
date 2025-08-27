# AgencySales Pro

## Overview

AgencySales Pro is a multi-agency sales management system built with Flask. The application manages agencies, their salespersons, customers, products, and orders in a hierarchical structure where super admins oversee multiple agencies, each with their own users and data. The system supports role-based access control with different user types (super_admin, agency_admin, staff, salesperson) having varying levels of access and functionality.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Web Framework
The application uses Flask as the web framework with a modular blueprint-based architecture. Each major feature (auth, agency, customer, product, order, etc.) is organized into separate blueprints, providing clear separation of concerns and maintainability.

### Database Architecture
- **ORM**: SQLAlchemy with Flask-SQLAlchemy extension for database operations
- **Database Support**: Configurable database URI supporting SQLite (default) and PostgreSQL
- **Models**: Hierarchical data structure with Agency as the top-level entity, containing Users, Locations, Products, Customers, and Orders
- **Relationships**: Proper foreign key relationships ensure data integrity across agencies

### Authentication & Authorization
- **Session Management**: Flask sessions for web interface authentication
- **JWT Tokens**: JWT-based authentication for API endpoints using Flask-JWT-Extended
- **Role-Based Access**: Decorator-based role checking with agency-level data isolation
- **Password Security**: Werkzeug password hashing for secure credential storage

### Frontend Architecture
- **Template Engine**: Jinja2 templates with Bootstrap 5 dark theme
- **Responsive Design**: Mobile-first approach using Bootstrap grid system
- **Interactive Features**: Chart.js for data visualization, client-side form validation
- **Modular CSS/JS**: Organized static assets with custom styling and JavaScript utilities

### Data Management
- **Excel Integration**: Import/export functionality using pandas for product and order data
- **Activity Logging**: Comprehensive audit trail tracking user actions
- **File Handling**: Secure file upload processing with validation

### API Design
The system provides RESTful API endpoints alongside the web interface, allowing for potential mobile or third-party integrations. JWT authentication ensures secure API access with user-scoped data access.

## External Dependencies

### Core Framework Dependencies
- **Flask**: Web framework for application structure
- **Flask-SQLAlchemy**: Database ORM integration
- **Flask-JWT-Extended**: JWT token management for API authentication
- **Werkzeug**: WSGI utilities and password hashing

### Data Processing
- **pandas**: Excel/CSV import/export functionality
- **openpyxl**: Excel file processing engine

### Frontend Libraries
- **Bootstrap 5**: UI framework with dark theme support
- **Font Awesome**: Icon library for consistent visual elements
- **Chart.js**: JavaScript charting library for dashboard analytics

### Database Support
- **SQLite**: Default database for development and small deployments
- **PostgreSQL**: Production database option (configurable via DATABASE_URL)

### Development Tools
- **ProxyFix**: Werkzeug middleware for deployment behind reverse proxies
- **Python datetime/uuid**: Standard library modules for timestamps and unique identifiers

The application is designed to be deployment-ready with environment variable configuration for sensitive settings like database URLs, secret keys, and JWT tokens.
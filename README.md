# ERP Multi-Tenant System

A Django-based multi-tenant ERP (Enterprise Resource Planning) system that supports multiple isolated databases for different organizations.

## Features

- **Multi-Tenant Architecture**: Each tenant gets their own isolated PostgreSQL database
- **User Signup & Approval**: Users sign up and wait for admin approval
- **Database Management**: Admin can manage multiple PostgreSQL servers
- **Docker Integration**: Create PostgreSQL servers as Docker containers
- **Remote Server Support**: Connect to existing remote PostgreSQL servers
- **Complete ERP Modules**: Finance, HR, CRM, and more

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Main Database                            │
│  (erp_main - stores users, servers, tenant info)               │
└─────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
│  PostgreSQL       │ │  PostgreSQL       │ │  PostgreSQL       │
│  Server 1         │ │  Server 2         │ │  Server N         │
│  (Docker/Remote)  │ │  (Docker/Remote)  │ │  (Docker/Remote)  │
├───────────────────┤ ├───────────────────┤ ├───────────────────┤
│ tenant_db_1       │ │ tenant_db_3       │ │ tenant_db_5       │
│ tenant_db_2       │ │ tenant_db_4       │ │ tenant_db_6       │
└───────────────────┘ └───────────────────┘ └───────────────────┘
```

## Requirements

- Python 3.10+
- PostgreSQL 12+ (for main database)
- Docker (optional, for local PostgreSQL containers)

## Installation

### 1. Clone and Setup Virtual Environment

```bash
cd erpdjango
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment

Copy the example environment file and edit it:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
SECRET_KEY=your-secret-key-here
DEBUG=True
DB_NAME=erp_main
DB_USER=postgres
DB_PASSWORD=your-password
DB_HOST=localhost
DB_PORT=5432
```

### 3. Create Main Database

Create the main database for tenant management:

```sql
CREATE DATABASE erp_main;
```

### 4. Run Migrations

```bash
python manage.py migrate
```

### 5. Create Superuser

```bash
python manage.py createsuperuser
```

Or use the setup command:

```bash
python manage.py setup_tenants --email admin@example.com --password yourpassword
```

### 6. Start the Development Server

```bash
python manage.py runserver
```

Visit:
- **Home Page**: http://localhost:8000/
- **Admin Panel**: http://localhost:8000/admin/
- **ERP**: http://localhost:8000/erp/

## Usage Flow

### 1. Admin Setup

1. Login to the admin panel at `/admin/`
2. **Add PostgreSQL Server**:
   - For Docker: Click "PostgreSQL Servers" → "Create Docker Server"
   - For Remote: Click "PostgreSQL Servers" → "Add PostgreSQL Server"

### 2. User Registration

1. Users visit the home page and click "Sign Up"
2. Fill in the registration form
3. Account is created in "Pending" status

### 3. Admin Approval

1. Admin sees new user in "Users" section with "Pending" status
2. Click on the user and select "Approve User"
3. Select a PostgreSQL server for the new database
4. System creates a new database and runs migrations
5. User is now approved and can access the ERP

### 4. User Access

1. Approved user logs in
2. System routes them to their tenant database
3. User completes ERP setup wizard
4. User can now use all ERP features

## PostgreSQL Server Management

### Docker Servers (Local)

Perfect for development or small deployments:

1. Navigate to Admin → PostgreSQL Servers
2. Click "Create Docker Server"
3. Fill in:
   - **Name**: Display name for the server
   - **Port**: Host port (different from 5432 if main DB uses it)
   - **Password**: PostgreSQL admin password
4. System creates a Docker container with PostgreSQL

### Remote Servers

For production deployments with existing PostgreSQL infrastructure:

1. Navigate to Admin → PostgreSQL Servers
2. Click "Add PostgreSQL Server"
3. Fill in:
   - **Name**: Display name
   - **Server Type**: Remote Server
   - **Host**: Server hostname/IP
   - **Port**: PostgreSQL port
   - **Admin Username/Password**: Credentials for database creation

## Database Assignment

Each approved user needs a database assignment. Options:

### Create New Database (During Approval)

When approving a user, a new database is created on the selected server.

### Assign Existing Database

Multiple users can share a database by using "Assign Database" action.

### Roles

- **Owner**: Full access, can manage other users
- **Admin**: Full access to ERP features
- **User**: Standard ERP access
- **Read Only**: View-only access

## Management Commands

```bash
# Initial setup with Docker server
python manage.py setup_tenants --email admin@example.com --password pass --create-docker-server

# Run migrations on all tenant databases
python manage.py migrate_tenants

# Check server health
python manage.py check_servers
```

## ERP Modules

Once logged into the ERP, users have access to:

### Finance
- Customers & Invoicing
- Payments
- Expenses
- Journal Entries
- Financial Reports

### HR
- Employees
- Departments
- Attendance
- Leave Requests

### CRM
- Leads
- Campaigns
- Customer Interactions

### Suppliers
- Supplier Management
- Purchase Orders
- Supplier Payments

### Services
- Service Categories
- Quotes

## API

REST API endpoints are available at `/api/`:

```
GET /api/customers/
GET /api/invoices/
GET /api/employees/
...
```

API authentication uses session or token authentication.

## Configuration Options

### Settings Reference

| Setting | Default | Description |
|---------|---------|-------------|
| `DOCKER_ENABLED` | True | Enable Docker server creation |
| `DOCKER_POSTGRES_IMAGE` | postgres:15-alpine | Docker image for PostgreSQL |
| `DOCKER_NETWORK` | erp_network | Docker network name |

## Security Considerations

- Each tenant database has unique credentials
- Users can only access their assigned database
- Admin panel is separate from tenant data
- All passwords are properly hashed

## Troubleshooting

### Docker not available

```
Error: Docker is not available or not running
```

**Solution**: Ensure Docker is installed and running:
```bash
docker info
```

### Database connection refused

```
Error: could not connect to server: Connection refused
```

**Solution**: Check PostgreSQL is running and credentials are correct.

### Migration errors

If migrations fail on a tenant database:

1. Check the database status in admin
2. View the error message
3. Fix any missing dependencies
4. Re-run migrations from admin

## License

MIT License

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

# DNS Management System

A FastAPI-based web application for managing domains through the Dynu.com API. This application provides a user-friendly interface to manage multiple Dynu.com accounts and their associated domains.

## Features

- **Single User Authentication**: Secure login system for one user
- **Account Management**: Register and manage multiple Dynu.com API accounts
- **Domain Operations**:
  - List all domains for each account
  - Add single or multiple domains
  - Remove single or multiple domains
- **Modern Web Interface**: Bootstrap-based responsive UI
- **Dashboard**: Overview of accounts and quick access to domain management

## Prerequisites

- Python 3.8 or higher
- Dynu.com account with API access

## Installation

1. **Clone or download the project files**

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   python main.py
   ```

4. **Access the application**:
   Open your browser and navigate to `http://localhost:8000`

## Getting Started

### 1. Register a User Account
- Navigate to `http://localhost:8000/register`
- Create your username and password
- This will be the only user account for the application

### 2. Login
- Use your credentials to login at `http://localhost:8000`

### 3. Add Dynu.com API Account
- Go to "Manage Accounts" from the dashboard
- Add your Dynu.com API key and account name
- You can get your API key from [Dynu.com Control Panel](https://www.dynu.com/en-US/ControlPanel/APICredentials)

### 4. Manage Domains
- Select an account from the dashboard
- View all domains associated with that account
- Add new domains (one per line in the text area)
- Remove domains (select single or multiple domains)

## API Endpoints

### Authentication
- `GET /` - Login page
- `POST /login` - User login
- `GET /register` - Registration page
- `POST /register` - User registration
- `GET /logout` - User logout

### Dashboard
- `GET /dashboard` - Main dashboard

### Account Management
- `GET /accounts` - Account management page
- `POST /accounts` - Create new account
- `GET /accounts/{account_id}/delete` - Delete account

### Domain Management
- `GET /domains/{account_id}` - Domain management page
- `POST /domains/{account_id}/add` - Add domains
- `POST /domains/{account_id}/delete` - Delete domains

## Configuration

### Security Settings
- Change the `SECRET_KEY` in `main.py` for production use
- The default token expiration is 30 minutes

### Database
- Uses SQLite database (`dns_management.db`)
- Database is created automatically on first run

## File Structure

```
DNS_management/
├── main.py              # Main FastAPI application
├── routes.py            # Route definitions
├── requirements.txt     # Python dependencies
├── README.md           # This file
├── templates/          # HTML templates
│   ├── base.html       # Base template
│   ├── login.html      # Login page
│   ├── register.html   # Registration page
│   ├── dashboard.html  # Dashboard
│   ├── accounts.html   # Account management
│   └── domains.html    # Domain management
└── static/            # Static files (empty, using CDN)
```

## Dynu.com API Integration

The application integrates with Dynu.com's API v2 to:
- Retrieve domain lists
- Add new domains
- Delete existing domains

Make sure you have a valid API key from your Dynu.com control panel.

## Security Notes

- **Production Use**: Change the `SECRET_KEY` in `main.py`
- **HTTPS**: Use HTTPS in production environments
- **API Keys**: API keys are stored in the database - ensure proper database security
- **Single User**: This application is designed for single-user use

## Troubleshooting

### Common Issues

1. **Import Errors**: Make sure all dependencies are installed
2. **Database Errors**: Delete `dns_management.db` to reset the database
3. **API Errors**: Verify your Dynu.com API key is valid and active
4. **Port Conflicts**: Change the port in `main.py` if 8000 is already in use

### Logs
Check the console output for detailed error messages and API responses.

## License

This project is provided as-is for educational and personal use.

#!/bin/bash

# DNS Management System - Quick Deploy (Skip package installation)
# Run this script from /var/www/dns-management directory

set -e  # Exit on any error

APP_DIR="/var/www/dns-management"

echo "🚀 Starting quick deployment of DNS Management System..."

# Check if we're in the right directory
if [[ ! -f "main.py" ]]; then
    echo "❌ Please run this script from /var/www/dns-management directory"
    echo "   Current directory: $(pwd)"
    exit 1
fi

echo "📁 Using existing directory: $APP_DIR"
echo "👤 Using current user: $(whoami)"

cd $APP_DIR

# Create virtual environment (try different methods)
echo "🐍 Setting up Python virtual environment..."
if python3 -m venv venv 2>/dev/null; then
    echo "✅ Created venv using python3 -m venv"
elif python3 -m virtualenv venv 2>/dev/null; then
    echo "✅ Created venv using python3 -m virtualenv"
else
    echo "📦 Installing virtualenv..."
    pip3 install virtualenv
    virtualenv -p python3 venv
    echo "✅ Created venv using virtualenv"
fi

# Upgrade pip
echo "📦 Upgrading pip..."
venv/bin/pip install --upgrade pip

# Install dependencies
echo "📦 Installing Python dependencies..."
venv/bin/pip install -r requirements.txt

# Create .env file from example
if [ ! -f .env ]; then
    echo "⚙️ Creating environment configuration..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your production settings!"
    echo "   Especially change the SECRET_KEY!"
fi

# Configure firewall for direct access
echo "🔥 Configuring firewall..."
firewall-cmd --permanent --add-service=ssh 2>/dev/null || echo "SSH service already configured"
firewall-cmd --permanent --add-port=8003/tcp 2>/dev/null || echo "Port 8003 already configured"
firewall-cmd --reload

# Kill any existing processes
echo "🛑 Stopping any existing processes..."
pkill -f "gunicorn.*main:app" || true
pkill -f "python.*main.py" || true

# Start application with nohup
echo "🚀 Starting application in background..."
nohup venv/bin/gunicorn -c gunicorn.conf.py main:app > dns_management.log 2>&1 &

# Get the process ID
sleep 2
PID=$(pgrep -f "gunicorn.*main:app" | head -1)

if [ ! -z "$PID" ]; then
    echo "✅ Application started successfully with PID: $PID"
    echo "📊 Process details:"
    ps aux | grep $PID | grep -v grep
else
    echo "❌ Failed to start application"
    echo "📋 Check logs: tail -f dns_management.log"
    exit 1
fi

echo ""
echo "✅ Quick deployment completed successfully!"
echo ""
echo "🌐 Your DNS Management System is now accessible at:"
echo "   http://YOUR_SERVER_IP:8003"
echo ""
echo "📋 Next steps:"
echo "   1. Edit .env with your production settings: nano .env"
echo "   2. Generate a secure SECRET_KEY: python3 -c \"import secrets; print(secrets.token_urlsafe(32))\""
echo "   3. Restart app: pkill -f gunicorn && nohup venv/bin/gunicorn -c gunicorn.conf.py main:app > dns_management.log 2>&1 &"
echo ""
echo "🔍 Useful commands:"
echo "   - Check logs: tail -f dns_management.log"
echo "   - Check process: ps aux | grep gunicorn"
echo "   - Stop app: pkill -f \"gunicorn.*main:app\""
echo "   - Test access: curl http://localhost:8003"
echo "   - View PID: pgrep -f \"gunicorn.*main:app\""
echo ""

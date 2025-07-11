#!/bin/bash

# MonitorDimmer Application Runner
# This script handles the complete setup and execution of the MonitorDimmer app

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKEND_DIR="backend"
FRONTEND_DIR="frontend"
DEFAULT_PORT=8080
MAX_PORT=8099
BACKEND_PORT=""
ELECTRON_PID=""

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}Shutting down MonitorDimmer...${NC}"
    
    # Kill Electron frontend if running (it will handle Python backend cleanup)
    if [ ! -z "$ELECTRON_PID" ] && kill -0 $ELECTRON_PID 2>/dev/null; then
        echo "Stopping Electron frontend (PID: $ELECTRON_PID)..."
        kill $ELECTRON_PID
        wait $ELECTRON_PID 2>/dev/null || true
    fi
    
    # Kill any remaining processes on the backend port as backup
    lsof -ti:$BACKEND_PORT | xargs kill -9 2>/dev/null || true
    
    echo -e "${GREEN}MonitorDimmer stopped successfully${NC}"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM EXIT

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if port is available
port_available() {
    ! lsof -i:$1 >/dev/null 2>&1
}

# Function to find an available port
find_available_port() {
    for port in $(seq $DEFAULT_PORT $MAX_PORT); do
        if port_available $port; then
            echo $port
            return 0
        fi
    done
    
    # If no port in range is available, try a random high port
    local random_port=$(python3 -c "import socket; s=socket.socket(); s.bind(('',0)); print(s.getsockname()[1]); s.close()")
    echo $random_port
}

# Print header
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}     MonitorDimmer Application        ${NC}"
echo -e "${BLUE}======================================${NC}"

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command_exists python3; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    exit 1
fi

if ! command_exists poetry; then
    echo -e "${RED}Error: Poetry is not installed${NC}"
    echo "Please install Poetry: https://python-poetry.org/docs/#installation"
    exit 1
fi

if ! command_exists node; then
    echo -e "${RED}Error: Node.js is not installed${NC}"
    echo "Please install Node.js: https://nodejs.org/"
    exit 1
fi

if ! command_exists npm; then
    echo -e "${RED}Error: npm is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ All prerequisites found${NC}"

# Clear Python cache files to ensure fresh code execution
echo -e "\n${YELLOW}Clearing Python cache files...${NC}"
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
echo -e "${GREEN}✓ Python cache cleared${NC}"

# Find an available port for the backend
echo -e "\n${YELLOW}Finding available port for backend...${NC}"
BACKEND_PORT=$(find_available_port)
echo -e "${GREEN}✓ Found available port: $BACKEND_PORT${NC}"

# Install backend dependencies
echo -e "\n${YELLOW}Setting up Python backend...${NC}"
cd "$BACKEND_DIR"

if [ ! -f "pyproject.toml" ]; then
    echo "Initializing Poetry project..."
    poetry init --no-interaction --name "monitor-dimmer-backend" --version "1.0.0"
fi

echo "Installing Python dependencies..."
poetry install --no-dev 2>/dev/null || poetry install

# Add required dependencies if not present
poetry add aiohttp pyobjc-framework-Cocoa pyobjc-framework-Quartz pyobjc-core 2>/dev/null || true

cd ..
echo -e "${GREEN}✓ Backend setup complete${NC}"

# Install frontend dependencies
echo -e "\n${YELLOW}Setting up Electron frontend...${NC}"
cd "$FRONTEND_DIR"

if [ ! -d "node_modules" ]; then
    echo "Installing Node.js dependencies..."
    npm install
else
    echo "Node.js dependencies already installed"
fi

cd ..
echo -e "${GREEN}✓ Frontend setup complete${NC}"

# Start Electron frontend (which will manage the Python backend)
echo -e "\n${YELLOW}Starting Electron frontend...${NC}"
cd "$FRONTEND_DIR"
BACKEND_PORT=$BACKEND_PORT npm start &
ELECTRON_PID=$!
cd ..

echo -e "\n${GREEN}✓ MonitorDimmer started successfully!${NC}"
echo -e "${BLUE}Electron PID: $ELECTRON_PID${NC}"
echo -e "${BLUE}Backend will be managed by Electron on: http://localhost:$BACKEND_PORT${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the application${NC}"

# Wait for Electron to finish
wait $ELECTRON_PID 2>/dev/null || true 
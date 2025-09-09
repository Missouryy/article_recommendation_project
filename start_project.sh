#!/bin/bash

# Academic Paper Recommendation System Startup Script for macOS/Linux
# Please ensure Python 3.8+ and Node.js 16+ are installed

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

echo -e "${GREEN}Academic Paper Recommendation System Startup Script${NC}"
echo -e "${GREEN}====================================================${NC}"

# Check required tools
echo -e "${YELLOW}Checking environment...${NC}"

# Check Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1)
    echo -e "${GREEN}Python: $PYTHON_VERSION${NC}"
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_VERSION=$(python --version 2>&1)
    echo -e "${GREEN}Python: $PYTHON_VERSION${NC}"
    PYTHON_CMD="python"
else
    echo -e "${RED}Python not found, please install Python 3.8+ first${NC}"
    exit 1
fi

# Check Node.js
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version 2>&1)
    echo -e "${GREEN}Node.js: $NODE_VERSION${NC}"
else
    echo -e "${RED}Node.js not found, please install Node.js 16+ first${NC}"
    exit 1
fi

# Check npm
if command -v npm &> /dev/null; then
    NPM_VERSION=$(npm --version 2>&1)
    echo -e "${GREEN}npm: $NPM_VERSION${NC}"
else
    echo -e "${RED}npm not found${NC}"
    exit 1
fi

echo ""

# Get the current directory
CURRENT_DIR=$(pwd)
echo -e "${GRAY}Project root directory: $CURRENT_DIR${NC}"

# Verify we're in the correct directory
if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo -e "${RED}Error: Please run this script from the project root directory${NC}"
    echo -e "${RED}Expected directories: backend, frontend${NC}"
    exit 1
fi

# --- 1. Setup Python virtual environment and install backend dependencies ---
echo -e "${CYAN}Setting up backend environment...${NC}"

if [ ! -d "article_recommend" ]; then
    echo -e "${YELLOW}Creating Python virtual environment...${NC}"
    $PYTHON_CMD -m venv article_recommend
fi

echo -e "${YELLOW}Activating virtual environment...${NC}"
source article_recommend/bin/activate

if [ ! -f "backend/requirements.txt" ]; then
    echo -e "${RED}backend/requirements.txt file not found${NC}"
    exit 1
fi

echo -e "${YELLOW}Installing backend dependencies...${NC}"
pip install -r ./backend/requirements.txt

echo -e "${GREEN}Backend environment setup completed${NC}"
echo ""

# --- 2. Install frontend dependencies ---
echo -e "${CYAN}Setting up frontend environment...${NC}"

if [ ! -f "frontend/package.json" ]; then
    echo -e "${RED}frontend/package.json file not found${NC}"
    exit 1
fi

cd frontend
echo -e "${YELLOW}Installing frontend dependencies...${NC}"
npm install

# Install additional Tailwind CSS plugins
echo -e "${YELLOW}Installing Tailwind CSS plugins...${NC}"
npm install @tailwindcss/forms @tailwindcss/typography @tailwindcss/aspect-ratio

cd ..
echo -e "${GREEN}Frontend environment setup completed${NC}"
echo ""

# --- 3. Start services ---
echo -e "${CYAN}Starting services...${NC}"

# Start backend service (in new terminal)
echo -e "${YELLOW}Starting FastAPI backend service...${NC}"

# Create backend startup script
cat > start_backend.sh << EOF
#!/bin/bash
cd "$CURRENT_DIR"
source article_recommend/bin/activate
cd backend
echo -e "\${GREEN}FastAPI backend service starting...\${NC}"
echo -e "\${YELLOW}API URL: http://127.0.0.1:8000\${NC}"
echo -e "\${YELLOW}API Docs: http://127.0.0.1:8000/docs\${NC}"
echo -e "\${GRAY}Press Ctrl+C to stop service\${NC}"
$PYTHON_CMD start_dev.py
EOF

chmod +x start_backend.sh

# Start backend in new terminal (macOS)
if command -v osascript &> /dev/null; then
    # macOS - use AppleScript to open new terminal
    osascript -e "tell application \"Terminal\" to do script \"cd '$CURRENT_DIR' && ./start_backend.sh\""
else
    # Linux - use gnome-terminal or xterm
    if command -v gnome-terminal &> /dev/null; then
        gnome-terminal -- bash -c "cd '$CURRENT_DIR' && ./start_backend.sh; exec bash"
    elif command -v xterm &> /dev/null; then
        xterm -e "cd '$CURRENT_DIR' && ./start_backend.sh; exec bash" &
    else
        echo -e "${YELLOW}Could not open new terminal. Please run backend manually:${NC}"
        echo -e "${GRAY}cd '$CURRENT_DIR' && ./start_backend.sh${NC}"
    fi
fi

# Wait for backend to start
echo -e "${YELLOW}Waiting for backend service to start...${NC}"
echo -e "${YELLOW}This may take 10-15 seconds for first startup...${NC}"
sleep 10

# Start frontend service (in new terminal)
echo -e "${YELLOW}Starting Vue frontend development server...${NC}"

# Create frontend startup script
cat > start_frontend.sh << EOF
#!/bin/bash
cd "$CURRENT_DIR"
cd frontend
echo -e "\${GREEN}Vue frontend development server starting...\${NC}"
echo -e "\${YELLOW}Frontend URL: http://localhost:5173\${NC}"
echo -e "\${GRAY}Press Ctrl+C to stop service\${NC}"
npm run dev
EOF

chmod +x start_frontend.sh

# Start frontend in new terminal (macOS)
if command -v osascript &> /dev/null; then
    # macOS - use AppleScript to open new terminal
    osascript -e "tell application \"Terminal\" to do script \"cd '$CURRENT_DIR' && ./start_frontend.sh\""
else
    # Linux - use gnome-terminal or xterm
    if command -v gnome-terminal &> /dev/null; then
        gnome-terminal -- bash -c "cd '$CURRENT_DIR' && ./start_frontend.sh; exec bash"
    elif command -v xterm &> /dev/null; then
        xterm -e "cd '$CURRENT_DIR' && ./start_frontend.sh; exec bash" &
    else
        echo -e "${YELLOW}Could not open new terminal. Please run frontend manually:${NC}"
        echo -e "${GRAY}cd '$CURRENT_DIR' && ./start_frontend.sh${NC}"
    fi
fi

echo ""
echo -e "${GREEN}Project startup completed!${NC}"
echo -e "${GREEN}====================================================${NC}"
echo -e "${CYAN}Frontend Application: http://localhost:5173${NC}"
echo -e "${CYAN}Backend API: http://127.0.0.1:8000${NC}"
echo -e "${CYAN}API Documentation: http://127.0.0.1:8000/docs${NC}"
echo ""
echo -e "${YELLOW}Test Account:${NC}"
echo -e "${GRAY}   Username: student_zhang${NC}"
echo -e "${GRAY}   Password: password${NC}"
echo ""
echo -e "${YELLOW}Tips:${NC}"
echo -e "${GRAY}   - Wait for frontend compilation to complete, then visit http://localhost:5173${NC}"
echo -e "${GRAY}   - You can register a new account or use the test account to login${NC}"
echo -e "${GRAY}   - Press Ctrl+C in the terminal windows to stop the corresponding services${NC}"
echo ""
echo -e "${GRAY}Press any key to exit this window...${NC}"
read -n 1 -s

# Clean up temporary scripts
rm -f start_backend.sh start_frontend.sh

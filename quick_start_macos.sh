#!/bin/bash

# Academic Paper Recommendation System - macOS Quick Start
# Similar to quick_start.ps1 but for macOS

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;37m'
NC='\033[0m'

echo -e "${GREEN}🚀 Academic Paper Recommendation System - Quick Start${NC}"
echo -e "${GREEN}====================================================${NC}"

# Check if we're in the right directory
if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo -e "${YELLOW}❌ Please run this script from the project root directory${NC}"
    exit 1
fi

# Get current directory
CURRENT_DIR=$(pwd)
echo -e "${GRAY}Project directory: $CURRENT_DIR${NC}"

# Check if virtual environment exists
if [ ! -d "article_recommend" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found. Please run start_project.sh first${NC}"
    exit 1
fi

# Activate virtual environment
echo -e "${YELLOW}🔧 Activating virtual environment...${NC}"
source article_recommend/bin/activate

# Start backend in new terminal
echo -e "${YELLOW}🚀 Starting backend service...${NC}"
osascript -e "tell application \"Terminal\" to do script \"cd '$CURRENT_DIR' && source article_recommend/bin/activate && cd backend && echo '🤖 Backend starting...' && echo 'Backend API: http://127.0.0.1:8000' && echo 'API Docs: http://127.0.0.1:8000/docs' && python start_dev.py\""

# Wait for backend to start
echo -e "${YELLOW}⏱️  Waiting for backend to initialize...${NC}"
echo -e "${GRAY}This may take 10-15 seconds for first startup...${NC}"
sleep 10

# Start frontend in new terminal
echo -e "${YELLOW}🚀 Starting frontend service...${NC}"
osascript -e "tell application \"Terminal\" to do script \"cd '$CURRENT_DIR' && cd frontend && echo '🌐 Frontend starting...' && echo 'Frontend URL: http://localhost:5173' && npm run dev\""

echo ""
echo -e "${GREEN}✅ Services starting...${NC}"
echo -e "${CYAN}🌐 Frontend: http://localhost:5173${NC}"
echo -e "${CYAN}🔧 Backend API: http://127.0.0.1:8000${NC}"
echo -e "${CYAN}📖 API Docs: http://127.0.0.1:8000/docs${NC}"
echo ""
echo -e "${YELLOW}💡 Test Account:${NC}"
echo -e "${GRAY}   Username: student_zhang${NC}"
echo -e "${GRAY}   Password: password${NC}"
echo ""
echo -e "${YELLOW}📝 Note: Two new Terminal windows will open for backend and frontend services${NC}"
echo -e "${GRAY}   Close those windows to stop the services${NC}"

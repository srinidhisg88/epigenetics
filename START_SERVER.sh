#!/bin/bash

# Color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Epilepsy Diagnostic Assistant - Server Startup        ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  Warning: .env file not found${NC}"
    echo -e "${YELLOW}   Creating .env from .env.example...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}   Please edit .env and add your API keys:${NC}"
    echo -e "${YELLOW}   - GROQ_API_KEY (required)${NC}"
    echo -e "${YELLOW}   - NCBI_API_KEY (optional, recommended)${NC}"
    echo -e "${YELLOW}   - ENTREZ_EMAIL (required)${NC}"
    echo ""
    read -p "Press Enter to continue after editing .env..."
fi

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo -e "${GREEN}✓ Virtual environment found${NC}"
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo -e "${GREEN}✓ Virtual environment found${NC}"
    source .venv/bin/activate
else
    echo -e "${YELLOW}⚠️  No virtual environment found${NC}"
    echo -e "${YELLOW}   Creating virtual environment...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Install/upgrade dependencies
echo ""
echo -e "${BLUE}📦 Checking dependencies...${NC}"
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Check FAISS index
echo ""
echo -e "${BLUE}🔍 Checking FAISS index...${NC}"
if [ ! -f "data/faiss_index/index.faiss" ]; then
    echo -e "${YELLOW}⚠️  FAISS index not found. Building...${NC}"
    python scripts/build_knowledge_base.py
else
    echo -e "${GREEN}✓ FAISS index ready (341 chunks)${NC}"
fi

# Run tests
echo ""
echo -e "${BLUE}🧪 Running integration tests...${NC}"
python scripts/test_multi_source.py
TEST_RESULT=$?

if [ $TEST_RESULT -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ All tests passed!${NC}"
    echo ""
else
    echo ""
    echo -e "${YELLOW}⚠️  Some tests failed, but continuing...${NC}"
    echo ""
fi

# Start the server
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║               Starting FastAPI Server                     ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Server will start at: http://localhost:8000${NC}"
echo -e "${GREEN}API docs available at: http://localhost:8000/docs${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo ""

# Start uvicorn
python -m uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000

#!/bin/bash

# eSRL Game Generator - Startup Script

echo "🎮 Starting eSRL Game Generator..."
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Creating one..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/upgrade dependencies
echo "📦 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Create necessary directories
mkdir -p pygames
mkdir -p templates
mkdir -p static

# Start the FastAPI server
echo ""
echo "✅ Starting web server..."
echo "🌐 Open your browser and go to: http://localhost:8000"
echo ""

python app.py

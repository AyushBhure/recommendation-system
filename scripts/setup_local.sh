#!/bin/bash
# Local development setup script
# Installs Python dependencies and sets up the environment

set -e

echo "=========================================="
echo "Setting up Local Development Environment"
echo "=========================================="

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Check Python version
echo ""
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo ""
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install root dependencies
echo ""
echo "Installing root dependencies..."
pip install -r requirements.txt

# Install service dependencies
echo ""
echo "Installing service dependencies..."
pip install -r services/ingest/requirements.txt
pip install -r services/serve/requirements.txt
pip install -r services/stream_processor/requirements.txt
pip install -r services/trainer/requirements.txt
pip install -r shared/requirements.txt

# Install pre-commit hooks
echo ""
echo "Installing pre-commit hooks..."
pre-commit install || echo "Pre-commit not available, skipping..."

echo ""
echo "=========================================="
echo "✓ Setup complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Activate virtual environment: source venv/bin/activate"
echo "  2. Copy .env.example to .env and configure"
echo "  3. Start services: ./scripts/dev_local_up.sh"
echo ""


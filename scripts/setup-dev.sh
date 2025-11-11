#!/bin/bash

# Development Environment Setup Script
# Sets up local development environment for Zapier Triggers API

set -e

echo "========================================"
echo "Zapier Triggers API - Development Setup"
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
  echo -e "${GREEN}✓${NC} $1"
}

print_error() {
  echo -e "${RED}✗${NC} $1"
}

print_warning() {
  echo -e "${YELLOW}⚠${NC} $1"
}

# Check prerequisites
echo ""
echo "Checking prerequisites..."

# Check Python
if command -v python3.11 &> /dev/null; then
  print_status "Python 3.11 found: $(python3.11 --version)"
else
  print_error "Python 3.11 not found. Please install Python 3.11."
  exit 1
fi

# Check Poetry
if command -v poetry &> /dev/null; then
  print_status "Poetry found: $(poetry --version)"
else
  print_warning "Poetry not found. Installing..."
  curl -sSL https://install.python-poetry.org | python3 -
  export PATH="$HOME/.local/bin:$PATH"
fi

# Check Docker
if command -v docker &> /dev/null; then
  print_status "Docker found: $(docker --version)"
else
  print_error "Docker not found. Please install Docker."
  exit 1
fi

# Check Docker Compose
if command -v docker-compose &> /dev/null; then
  print_status "Docker Compose found: $(docker-compose --version)"
else
  print_error "Docker Compose not found. Please install Docker Compose."
  exit 1
fi

# Check AWS CLI
if command -v aws &> /dev/null; then
  print_status "AWS CLI found: $(aws --version)"
else
  print_warning "AWS CLI not found. Some features may not work."
fi

# Check Terraform
if command -v terraform &> /dev/null; then
  print_status "Terraform found: $(terraform version -json | jq -r '.terraform_version')"
else
  print_warning "Terraform not found. Infrastructure deployment will not work."
fi

# Install backend dependencies
echo ""
echo "Installing backend dependencies..."
cd services/api
poetry install
print_status "Backend dependencies installed"
cd ../..

# Create .env file if it doesn't exist
echo ""
if [ ! -f .env ]; then
  echo "Creating .env file..."
  cp .env.example .env
  print_status ".env file created"
else
  print_warning ".env file already exists"
fi

# Start LocalStack
echo ""
echo "Starting LocalStack..."
docker-compose up -d
sleep 10  # Wait for LocalStack to start
print_status "LocalStack started"

# Verify LocalStack
echo ""
echo "Verifying LocalStack..."
if curl -s http://localhost:4566/_localstack/health | grep -q '"dynamodb": "available"'; then
  print_status "LocalStack is healthy"
else
  print_warning "LocalStack may not be fully ready. Run 'docker-compose logs localstack' to check."
fi

echo ""
echo "========================================"
echo "Setup complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Start development: docker-compose up"
echo "  2. Run tests: cd services/api && poetry run pytest"
echo "  3. Deploy to AWS: cd infrastructure/terraform/environments/dev && terraform apply"
echo ""
echo "LocalStack is running at: http://localhost:4566"
echo "Use AWS CLI with: aws --endpoint-url=http://localhost:4566 ..."
echo ""

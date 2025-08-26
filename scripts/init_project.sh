#!/bin/bash

# Initialize API Key Manager project
# Sets up environment and generates secrets

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 Initializing API Key Manager"
echo "==============================="

# Check if .env already exists
ENV_FILE="$PROJECT_ROOT/.env"
if [ -f "$ENV_FILE" ]; then
    echo "⚠️  .env file already exists"
    read -p "Do you want to overwrite it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Cancelled"
        exit 1
    fi
fi

# Copy env.example to .env
echo "📄 Creating .env from env.example..."
cp "$PROJECT_ROOT/env.example" "$ENV_FILE"

# Run secrets setup
echo "🔐 Generating secrets..."
"$SCRIPT_DIR/setup_secrets.sh"

echo ""
echo "🎉 Project initialized successfully!"
echo ""
echo "📁 Files created/updated:"
echo "- .env (with generated secrets)"
echo "- redis_users.acl (with generated password)"
echo ""
echo "🚀 Ready to deploy:"
echo "   docker-compose up --build -d"
echo ""
echo "💡 Tip: Your secrets are in .env - keep this file secure and don't commit it!"

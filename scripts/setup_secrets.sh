#!/bin/bash

# Setup script for API Key Manager
# Generates secure passwords and configures the system

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🔐 Setting up API Key Manager Secrets"
echo "====================================="

# Function to generate secure password without problematic characters
generate_password() {
    openssl rand -base64 32 | tr '+/' 'AB' | head -c 32
}

# Generate passwords
REDIS_VALIDATOR_PASSWORD=$(generate_password)
REDIS_MANAGER_PASSWORD=$(generate_password)
ADMIN_SECRET=$(generate_password)

echo ""
echo "✅ Generated secure passwords"

# Create/update .env file
ENV_FILE="$PROJECT_ROOT/.env"
ENV_EXAMPLE="$PROJECT_ROOT/env.example"

if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$ENV_EXAMPLE" ]; then
        echo "📝 Creating .env file from env.example..."
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        echo "✅ Created .env file"
    else
        echo "❌ env.example file not found at $ENV_EXAMPLE"
        exit 1
    fi
else
    echo "📝 Updating existing .env file..."
    
    # Create backup
    cp "$ENV_FILE" "$ENV_FILE.backup.$(date +%s)"
    echo "💾 Created backup of existing .env file"
fi

# Update passwords in .env file
sed -i.tmp "s/REDIS_VALIDATOR_PASSWORD=.*/REDIS_VALIDATOR_PASSWORD=$REDIS_VALIDATOR_PASSWORD/" "$ENV_FILE"
sed -i.tmp "s/REDIS_MANAGER_PASSWORD=.*/REDIS_MANAGER_PASSWORD=$REDIS_MANAGER_PASSWORD/" "$ENV_FILE"
sed -i.tmp "s/ADMIN_SECRET=.*/ADMIN_SECRET=$ADMIN_SECRET/" "$ENV_FILE"
rm "$ENV_FILE.tmp"

echo "✅ Updated .env file with secure passwords"

# Create/update Redis ACL file
ACL_FILE="$PROJECT_ROOT/redis_users.acl"
ACL_EXAMPLE="$PROJECT_ROOT/redis_users.acl.example"

if [ ! -f "$ACL_FILE" ]; then
    if [ -f "$ACL_EXAMPLE" ]; then
        echo "📝 Creating redis_users.acl file from redis_users.acl.example..."
        cp "$ACL_EXAMPLE" "$ACL_FILE"
        echo "✅ Created redis_users.acl file"
    else
        echo "❌ redis_users.acl.example file not found at $ACL_EXAMPLE"
        exit 1
    fi
else
    echo "📝 Updating existing redis_users.acl file..."
    
    # Create backup
    cp "$ACL_FILE" "$ACL_FILE.backup.$(date +%s)"
    echo "💾 Created backup of existing redis_users.acl file"
fi

# Update passwords in ACL file
sed -i.tmp "s/>CHANGE_ME_GENERATE_SECURE_VALIDATOR_PASSWORD/>$REDIS_VALIDATOR_PASSWORD/" "$ACL_FILE"
sed -i.tmp "s/>CHANGE_ME_GENERATE_SECURE_MANAGER_PASSWORD/>$REDIS_MANAGER_PASSWORD/" "$ACL_FILE"
sed -i.tmp "s/>VALIDATOR_PASSWORD_PLACEHOLDER/>$REDIS_VALIDATOR_PASSWORD/" "$ACL_FILE"
rm "$ACL_FILE.tmp"

echo "✅ Updated redis_users.acl file with secure passwords"

echo ""
echo "🎉 Setup complete!"
echo ""
echo "📋 Configuration Summary:"
echo "========================"
echo "Redis Validator Password: $REDIS_VALIDATOR_PASSWORD"
echo "Redis Manager Password: $REDIS_MANAGER_PASSWORD"
echo "Admin Secret: $ADMIN_SECRET"
echo ""
echo "🚀 Next steps:"
echo "1. Run: docker-compose up --build -d"
echo "2. Test health: curl http://localhost:12818/health"
echo ""
echo "🧪 Test admin endpoints with:"
echo "curl -H \"Authorization: Bearer $ADMIN_SECRET\" \\"
echo "     -X POST \"http://localhost:12818/v1/admin/create-project?project_id=test&label=Test&owner=admin\""
echo ""
echo "⚠️  Keep these secrets secure!"
echo "💾 Backups created with timestamp suffix"

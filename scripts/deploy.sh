#!/bin/bash

# Load environment variables from .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
else
    echo "❌ .env file not found!"
    echo "Please create a .env file with your Home Assistant server details."
    exit 1
fi

# Validate required environment variables
required_vars=("HA_SERVER_HOST" "HA_SERVER_USER" "HA_SERVER_PASSWORD" "HA_SERVER_PATH")
missing_vars=()

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo "❌ Missing required environment variables:"
    for var in "${missing_vars[@]}"; do
        echo "   - $var"
    done
    echo ""
    echo "Please update your .env file with the correct values."
    exit 1
fi

# Set default port if not specified
if [ -z "$HA_SERVER_PORT" ]; then
    HA_SERVER_PORT=22
fi

# Build paths
backend_source="$(pwd)/custom_components/rbac"
backend_target="$HA_SERVER_USER@$HA_SERVER_HOST:$HA_SERVER_PATH"

# Check if source directory exists
if [ ! -d "$backend_source" ]; then
    echo "❌ Backend source directory not found: $backend_source"
    exit 1
fi

echo "🚀 Deploying RBAC Middleware integration to Home Assistant..."
echo "📁 Backend Source: $backend_source"
echo "🎯 Backend Target: $backend_target"
echo ""

# Deploy backend (custom_components)
backend_scp_command="sshpass -p \"$HA_SERVER_PASSWORD\" scp -r \"$backend_source\" \"$backend_target\""
if [ "$HA_SERVER_PORT" != "22" ]; then
    backend_scp_command="sshpass -p \"$HA_SERVER_PASSWORD\" scp -P $HA_SERVER_PORT -r \"$backend_source\" \"$backend_target\""
fi

echo "📦 Deploying RBAC Middleware integration..."
if eval "$backend_scp_command"; then
    echo "✅ Integration deployment successful!"
else
    echo "❌ Integration deployment failed!"
    exit 1
fi

echo ""
echo "🔄 Restarting Home Assistant..."
    
# Restart Home Assistant core
restart_command="sshpass -p \"$HA_SERVER_PASSWORD\" ssh -o StrictHostKeyChecking=no"
if [ "$HA_SERVER_PORT" != "22" ]; then
    restart_command="$restart_command -p $HA_SERVER_PORT"
fi
restart_command="$restart_command $HA_SERVER_USER@$HA_SERVER_HOST 'ha core restart'"

if eval "$restart_command"; then
    echo "✅ Home Assistant restart initiated!"
    echo ""
    echo "📋 Next steps:"
    echo "   1. Wait for Home Assistant to restart (usually 1-2 minutes)"
    echo "   2. Check the logs for \"RBAC Middleware\" messages"
    echo "   3. Add the integration via Settings → Devices & Services"
    echo "   4. Configure access control in access_control.yaml file"
    echo "   5. Use the RBAC services to manage user access"
    echo ""
    echo "🔗 Access your Home Assistant at: http://$HA_SERVER_HOST:8123"
else
    echo "⚠️  Deployment successful but restart failed!"
    echo "Please manually restart Home Assistant."
fi



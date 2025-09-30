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
required_vars=("HA_SERVER_HOST" "HA_SERVER_USER" "HA_SERVER_PASSWORD")
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
frontend_dir="$(pwd)/frontend"
frontend_source="$(pwd)/www/community/rbac"
frontend_target="$HA_SERVER_USER@$HA_SERVER_HOST:/config/www/community/rbac"

# Check if frontend directory exists
if [ ! -d "$frontend_dir" ]; then
    echo "❌ Frontend directory not found: $frontend_dir"
    exit 1
fi

echo "🚀 Building and Deploying RBAC Preact Frontend to Home Assistant..."
echo "📁 Frontend Directory: $frontend_dir"
echo "🎯 Frontend Target: $frontend_target"
echo ""

# Navigate to frontend directory and build
cd "$frontend_dir"

echo "📦 Installing dependencies..."
if [ ! -d "node_modules" ]; then
    npm install
else
    echo "Dependencies already installed, skipping..."
fi

echo "🔨 Building Preact frontend..."
npm run build

# Check if build was successful
if [ ! -f "../www/community/rbac/config.html" ]; then
    echo "❌ Build failed - config.html not found in ../www/community/rbac/"
    exit 1
fi

# Deploy frontend (built files) - copy both HTML and JS files
frontend_scp_command="sshpass -p \"$HA_SERVER_PASSWORD\" scp \"$frontend_source\"/src/index.html \"$frontend_target\"/config.html"
if [ "$HA_SERVER_PORT" != "22" ]; then
    frontend_scp_command="sshpass -p \"$HA_SERVER_PASSWORD\" scp -P $HA_SERVER_PORT \"$frontend_source\"/src/index.html \"$frontend_target\"/config.html"
fi

echo "📤 Deploying RBAC frontend HTML..."
if eval "$frontend_scp_command"; then
    echo "✅ HTML deployment successful!"
else
    echo "❌ HTML deployment failed!"
    exit 1
fi

# Deploy the JavaScript file
frontend_scp_command="sshpass -p \"$HA_SERVER_PASSWORD\" scp \"$frontend_source\"/config.js \"$frontend_target\"/"
if [ "$HA_SERVER_PORT" != "22" ]; then
    frontend_scp_command="sshpass -p \"$HA_SERVER_PASSWORD\" scp -P $HA_SERVER_PORT \"$frontend_source\"/config.js \"$frontend_target\"/"
fi

echo "📤 Deploying RBAC frontend JavaScript..."
if eval "$frontend_scp_command"; then
    echo "✅ Frontend deployment successful!"
    echo ""
    echo "📋 Next steps:"
    echo "   1. Reload the frontend (refresh browser or restart Home Assistant)"
    echo "   2. Navigate to: http://$HA_SERVER_HOST:8123/local/community/rbac/config.html"
    echo "   3. Check browser console (F12) for any errors"
    echo ""
    echo "🔗 Access your Home Assistant at: http://$HA_SERVER_HOST:8123"
else
    echo "❌ Frontend deployment failed!"
    exit 1
fi

#!/bin/bash

# Build paths
frontend_dir="frontend"
frontend_source="custom_components/rbac/www"
frontend_target="config/custom_components/rbac/www"

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
if [ ! -f "../custom_components/rbac/www/config.html" ]; then
    echo "❌ Build failed - config.html not found in ../custom_components/rbac/www/"
    exit 1
fi

# Navigate back to the root directory
cd ..

# Create the frontend directory structure on the server first
echo "📁 Creating frontend directory structure..."
mkdir_command="sudo mkdir -p \"$frontend_target\""

if eval "$mkdir_command"; then
    echo "✅ Frontend directory structure created"
else
    echo "❌ Failed to create frontend directory structure"
    exit 1
fi

# Deploy frontend (built files) - copy both HTML and JS files
frontend_scp_command="sudo cp \"$frontend_source\"/src/index.html \"$frontend_target\"/config.html"

echo "📤 Deploying RBAC frontend HTML..."
if eval "$frontend_scp_command"; then
    echo "✅ HTML deployment successful!"
else
    echo "❌ HTML deployment failed!"
    exit 1
fi

# Deploy the JavaScript file
frontend_scp_command="sudo cp -p \"$frontend_source\"/config.js \"$frontend_target\"/"

echo "📤 Deploying RBAC frontend JavaScript..."
if eval "$frontend_scp_command"; then
    echo "✅ Frontend deployment successful!"
    echo "Please refresh the frontend cache to see the changes."
else
    echo "❌ Frontend deployment failed!"
    exit 1
fi

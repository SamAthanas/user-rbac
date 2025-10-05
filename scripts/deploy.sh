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

frontend_source="$(pwd)/custom_components/rbac/www"
frontend_target="$HA_SERVER_USER@$HA_SERVER_HOST:/config/custom_components/rbac/www"

# Check if source directories exist
if [ ! -d "$backend_source" ]; then
    echo "❌ Backend source directory not found: $backend_source"
    exit 1
fi

# Build frontend before deployment
frontend_dir="$(pwd)/frontend"
if [ -d "$frontend_dir" ]; then
    echo "🔨 Building Preact frontend..."
    cd "$frontend_dir"
    if npm run build; then
        echo "✅ Frontend build successful!"
        cd - > /dev/null
    else
        echo "❌ Frontend build failed!"
        cd - > /dev/null
        exit 1
    fi
else
    echo "⚠️  Frontend directory not found: $frontend_dir"
    echo "Skipping frontend build..."
fi

if [ ! -d "$frontend_source" ]; then
    echo "❌ Frontend source directory not found: $frontend_source"
    exit 1
fi

echo "🚀 Deploying RBAC Middleware integration to Home Assistant..."
echo "📁 Backend Source: $backend_source"
echo "🎯 Backend Target: $backend_target"
echo "📁 Frontend Source: $frontend_source"
echo "🎯 Frontend Target: $frontend_target"
echo ""

# Deploy backend (custom_components) - exclude access_control.yaml
echo "📦 Deploying RBAC Middleware integration..."

# Deploy individual files (excluding access_control.yaml)
for file in "$backend_source"/*; do
    if [ -f "$file" ]; then
        filename=$(basename "$file")
        if [ "$filename" != "access_control.yaml" ]; then
            echo "📄 Deploying $filename..."
            backend_scp_command="sshpass -p \"$HA_SERVER_PASSWORD\" scp \"$file\" \"$backend_target/rbac/\""
            if [ "$HA_SERVER_PORT" != "22" ]; then
                backend_scp_command="sshpass -p \"$HA_SERVER_PASSWORD\" scp -P $HA_SERVER_PORT \"$file\" \"$backend_target/rbac/\""
            fi
            
            if eval "$backend_scp_command"; then
                echo "✅ Deployed $filename"
            else
                echo "❌ Failed to deploy $filename"
                exit 1
            fi
        else
            echo "⏭️  Skipping $filename (preserving existing configuration)"
        fi
    fi
done

echo "✅ Backend deployment successful!"

# Deploy frontend (JavaScript files)
echo "📦 Deploying RBAC frontend files..."

# Create the frontend directory structure on the server first
echo "📁 Creating frontend directory structure..."
mkdir_command="sshpass -p \"$HA_SERVER_PASSWORD\" ssh -o StrictHostKeyChecking=no"
if [ "$HA_SERVER_PORT" != "22" ]; then
    mkdir_command="$mkdir_command -p $HA_SERVER_PORT"
fi
mkdir_command="$mkdir_command $HA_SERVER_USER@$HA_SERVER_HOST 'mkdir -p /config/custom_components/rbac/www'"

if eval "$mkdir_command"; then
    echo "✅ Frontend directory structure created"
else
    echo "❌ Failed to create frontend directory structure"
    exit 1
fi

# Deploy individual files (not directories)
for file in "$frontend_source"/*; do
    if [ -f "$file" ]; then
        filename=$(basename "$file")
        frontend_scp_command="sshpass -p \"$HA_SERVER_PASSWORD\" scp \"$file\" \"$frontend_target/$filename\""
        if [ "$HA_SERVER_PORT" != "22" ]; then
            frontend_scp_command="sshpass -p \"$HA_SERVER_PASSWORD\" scp -P $HA_SERVER_PORT \"$file\" \"$frontend_target/$filename\""
        fi
        
        if eval "$frontend_scp_command"; then
            echo "✅ Deployed $filename"
        else
            echo "❌ Failed to deploy $filename"
            exit 1
        fi
    fi
done

echo "✅ Frontend deployment successful!"

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
    echo "   1. Wait for Home Assistant to restart"
    echo "   2. Check the logs for \"RBAC Middleware\" messages"
    echo "   3. Add the integration via Settings → Devices & Services"
    echo "   4. Configure access control in access_control.yaml file"
    echo "   5. Add frontend JavaScript to configuration.yaml:"
    echo "      frontend:"
    echo "        extra_module_url:"
    echo "          - /api/rbac/static/rbac.js"
    echo "   6. Use the RBAC services to manage user access"
else
    echo "⚠️  Deployment successful but restart failed!"
    echo "Please manually restart Home Assistant."
fi



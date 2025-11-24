#!/bin/bash
#
# F1 Telemetry App - Modal Deployment Script
#
# This script automates the Modal deployment process:
# 1. Checks prerequisites
# 2. Creates volumes
# 3. Uploads cache (optional)
# 4. Deploys application
#
# Usage:
#   ./deploy-modal.sh                 # Full deployment
#   ./deploy-modal.sh --no-cache      # Skip cache upload
#   ./deploy-modal.sh --dev           # Development mode

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
VOLUME_NAME="f1-data"
CACHE_DIR="fastf1_cache"
UPLOAD_CACHE=true
DEV_MODE=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --no-cache)
            UPLOAD_CACHE=false
            shift
            ;;
        --dev)
            DEV_MODE=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --no-cache    Skip FastF1 cache upload"
            echo "  --dev         Development mode (serve instead of deploy)"
            echo "  --help        Show this help message"
            exit 0
            ;;
    esac
done

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Check prerequisites
log_info "Checking prerequisites..."

# Check if modal is installed
if ! command -v modal &> /dev/null; then
    log_error "Modal CLI not found. Installing..."
    pip install modal
fi
log_success "Modal CLI installed"

# Check if authenticated
if ! modal token get &> /dev/null; then
    log_warning "Not authenticated with Modal. Running setup..."
    modal setup
fi
log_success "Authenticated with Modal"

# Check if app file exists
if [ ! -f "app_modal.py" ]; then
    log_error "app_modal.py not found. Make sure you're in the project directory."
    exit 1
fi
log_success "Found app_modal.py"

# Create volume if it doesn't exist
log_info "Checking Modal volume..."
# Temporarily disable exit-on-error for volume operations
set +e
# Try to list the volume - if it fails, volume doesn't exist
if modal volume ls "$VOLUME_NAME" / &> /dev/null; then
    log_success "Volume '$VOLUME_NAME' already exists"
else
    log_info "Creating volume '$VOLUME_NAME'..."
    CREATE_OUTPUT=$(modal volume create "$VOLUME_NAME" 2>&1)
    if echo "$CREATE_OUTPUT" | grep -q "already exists"; then
        log_success "Volume '$VOLUME_NAME' already exists"
    elif [ $? -eq 0 ]; then
        log_success "Created volume '$VOLUME_NAME'"
    else
        log_error "Failed to create volume: $CREATE_OUTPUT"
        exit 1
    fi
fi
# Re-enable exit-on-error
set -e

# Upload cache if requested
if [ "$UPLOAD_CACHE" = true ]; then
    if [ -d "$CACHE_DIR" ]; then
        log_info "Uploading FastF1 cache (this may take a few minutes)..."

        # Count files
        FILE_COUNT=$(find "$CACHE_DIR" -type f | wc -l | tr -d ' ')
        CACHE_SIZE=$(du -sh "$CACHE_DIR" | cut -f1)

        log_info "Uploading $FILE_COUNT files ($CACHE_SIZE)..."

        if modal volume put "$VOLUME_NAME" "$CACHE_DIR" /fastf1_cache; then
            log_success "Cache uploaded successfully"
        else
            log_warning "Cache upload failed (continuing anyway)"
        fi
    else
        log_warning "Cache directory not found at '$CACHE_DIR' (will rebuild on first use)"
    fi
else
    log_info "Skipping cache upload (--no-cache)"
fi

# Deploy or serve
if [ "$DEV_MODE" = true ]; then
    log_info "Starting development mode (serve)..."
    log_info "App will auto-reload on file changes"
    log_info "Press Ctrl+C to stop"
    echo ""
    modal serve app_modal.py
else
    log_info "Deploying application to Modal..."
    echo ""
    modal deploy app_modal.py

    if [ $? -eq 0 ]; then
        echo ""
        log_success "Deployment successful! 🎉"
        echo ""
        log_info "Next steps:"
        echo "  1. Visit https://modal.com/apps to view your deployment"
        echo "  2. Test your app at the Flask URL shown above"
        echo "  3. Update your Cloudflare tunnel (optional)"
        echo ""
        log_info "To view logs: modal app logs f1-telemetry"
        log_info "To check costs: https://modal.com/usage"
        echo ""
        log_info "See DEPLOY_MODAL.md for detailed instructions"
    else
        log_error "Deployment failed"
        exit 1
    fi
fi

#!/bin/bash
# F1 Telemetry Health Check Script
# Runs periodically to verify all services are healthy and trigger Modal warmup

set -e

LOG_DIR="$HOME/Library/Logs/f1-telemetry"
LOG_FILE="$LOG_DIR/health.log"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG_FILE"
}

check_flask() {
    if curl -sf http://localhost:5151/ > /dev/null 2>&1; then
        return 0
    fi
    return 1
}

check_proxy() {
    if curl -sf http://localhost:11435/health > /dev/null 2>&1; then
        return 0
    fi
    return 1
}

check_cloudflare() {
    if curl -sf --max-time 10 https://f1.linux-box.cc/ > /dev/null 2>&1; then
        return 0
    fi
    return 1
}

warmup_modal() {
    # Trigger Modal warmup to reduce cold starts
    # This keeps the GPU container warm for the next 10 minutes
    response=$(curl -sf -X POST http://localhost:11435/warmup 2>&1) || true
    if echo "$response" | grep -q "warmed"; then
        log "INFO: Modal container warmed successfully"
    fi
}

# Main health check
HEALTHY=true
ERRORS=""

if ! check_flask; then
    ERRORS="$ERRORS Flask(5151)"
    HEALTHY=false
fi

if ! check_proxy; then
    ERRORS="$ERRORS Proxy(11435)"
    HEALTHY=false
fi

if ! check_cloudflare; then
    ERRORS="$ERRORS Cloudflare"
    # Don't mark as unhealthy - external connectivity issue
fi

if [ "$HEALTHY" = true ]; then
    log "OK: All services healthy"
    # Warmup Modal to reduce cold starts for next user
    warmup_modal
else
    log "ERROR: Services down:$ERRORS"

    # Optional: Send notification
    # osascript -e "display notification \"F1 Telemetry services down:$ERRORS\" with title \"Health Check Failed\""
fi

# F1 Telemetry Application - Hybrid Deployment Analysis

**Date:** January 8, 2026
**Status:** Production Analysis Complete
**Author:** Hybrid Cloud Architecture Review

---

## Executive Summary

The F1 telemetry application uses a hybrid deployment architecture combining local infrastructure with Modal serverless GPU compute. This analysis identifies current issues, proposes improvements, and provides a concrete implementation plan while maintaining the $0/month cost constraint.

**Current Architecture Verdict:** The hybrid approach is fundamentally sound but has operational gaps in monitoring, failover, and process management.

---

## 1. Current Architecture Overview

```
+------------------+     +---------------------+     +-------------------+
|                  |     |                     |     |                   |
|  Internet User   +---->+  Cloudflare Tunnel  +---->+  Local Machine    |
|                  |     |  (f1.linux-box.cc)  |     |  (macOS)          |
+------------------+     +---------------------+     +--------+----------+
                                                              |
                         +------------------------------------+------------------------------------+
                         |                                                                         |
                         v                                                                         v
              +----------+----------+                                              +---------------+--------------+
              |                     |                                              |                              |
              |  Flask Application  |   OLLAMA_BASE_URL=http://localhost:11435    |  Ollama Modal Proxy          |
              |  (localhost:5151)   +--------------------------------------------->+  (localhost:11435)           |
              |                     |                                              |                              |
              +----------+----------+                                              +---------------+--------------+
                         |                                                                         |
                         v                                                                         v
              +----------+----------+                                              +---------------+--------------+
              |                     |                                              |                              |
              |  FastF1 Cache       |                                              |  Modal T4 GPU Function       |
              |  (local disk)       |                                              |  (f1-ollama-gpu)             |
              |                     |                                              |                              |
              +---------------------+                                              +------------------------------+
```

### Component Summary

| Component | Location | Port | Purpose | Status |
|-----------|----------|------|---------|--------|
| Flask App | Local Mac | 5151 | Web UI, plot generation, FastF1 data | Running |
| Cloudflare Tunnel | Cloud | N/A | Public ingress at f1.linux-box.cc | Running |
| Ollama Proxy | Local Mac | 11435 | Bridge to Modal GPU | NOT Running |
| Modal GPU | Serverless | N/A | AI inference on T4 GPU | Deployed |
| FastF1 Cache | Local Disk | N/A | F1 telemetry data cache | Active |

---

## 2. Issues Identified

### 2.1 Critical Issues

#### ISSUE-1: Ollama Proxy Not Running
**Severity:** HIGH
**Impact:** AI analysis completely broken

The Ollama proxy (`deployment/ollama_modal_proxy.py`) is not running, meaning all AI inference requests fail with connection errors. The Flask app is running on port 5151 but cannot reach the GPU backend.

**Evidence:**
```bash
$ curl -s http://localhost:11435/health
# No response - proxy not running

$ ps aux | grep ollama_modal_proxy
# No matching processes
```

**Current behavior:** When a user clicks on a telemetry moment for AI analysis, the request fails with a 503 error.

#### ISSUE-2: No Process Manager
**Severity:** HIGH
**Impact:** Services don't restart after crashes/reboots

The production startup script (`scripts/start-production-gpu.sh`) runs processes in the foreground with basic shell backgrounding. There is no:
- Automatic restart on crash
- Boot-time service registration
- Health check monitoring
- Log rotation

**Current startup:**
```bash
uv run python deployment/ollama_modal_proxy.py > logs/proxy.log 2>&1 &
uv run python run.py
```

This means:
- If the machine reboots, services don't start
- If a service crashes, it stays down
- No automatic recovery

#### ISSUE-3: Cloudflare Tunnel Running as Background Process
**Severity:** MEDIUM
**Impact:** Tunnel disconnects go unnoticed

The Cloudflare tunnel is running as a simple background process rather than a managed service:
```bash
$ ps aux | grep cloudflared
will  4094  cloudflared tunnel run 65a1819f-0187-41c0-b525-9b909f142ff7
```

No automatic restart or health monitoring.

### 2.2 Performance Issues

#### ISSUE-4: Modal Cold Start Latency
**Severity:** MEDIUM
**Impact:** First AI request takes 15-20 seconds

When the Modal container is cold (idle > 10 minutes), the first inference request must:
1. Start the container (~5s)
2. Start Ollama service (~3s)
3. Check/pull model (~5s if cached)
4. Run inference (~5-10s)

**Total cold start:** 15-25 seconds

**Current mitigation:** `scaledown_window=600` keeps container warm for 10 minutes after last request.

#### ISSUE-5: No Warmup Trigger
**Severity:** LOW
**Impact:** Users experience cold start delays

The proxy has a `/warmup` endpoint but it is never called. Users hitting the site after 10+ minutes of inactivity experience full cold start latency.

### 2.3 Security Concerns

#### ISSUE-6: Modal Authentication via Environment
**Severity:** LOW
**Impact:** Credentials stored in shell environment

Modal authentication uses `~/.modal.toml` which is secure, but the proxy relies on implicit authentication. No explicit credential validation or rotation.

#### ISSUE-7: No Rate Limiting on Proxy
**Severity:** LOW
**Impact:** Potential for abuse

The Ollama proxy at localhost:11435 has no rate limiting. If exposed (which it isn't currently), it could be abused.

#### ISSUE-8: Flask Secret Key Fallback
**Severity:** LOW
**Impact:** Predictable session tokens in dev

```python
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'f1-telemetry-secret-key-change-in-production')
```

The fallback secret key is predictable. Production should ensure `.env.secret` exists.

### 2.4 Operational Issues

#### ISSUE-9: Logs Not Centralized
**Severity:** MEDIUM
**Impact:** Debugging requires checking multiple locations

Logs are scattered:
- Flask: stdout (lost if not redirected)
- Proxy: `logs/proxy.log` (if redirected)
- Cloudflare: `logs/cloudflared.log` (if redirected)
- Modal: `modal app logs` (remote)

No unified view or alerting.

#### ISSUE-10: No Health Monitoring
**Severity:** MEDIUM
**Impact:** Silent failures

No automated health checks to detect:
- Flask app down
- Proxy down
- Modal function unavailable
- Cloudflare tunnel disconnected

### 2.5 Reliability Issues

#### ISSUE-11: No Failover for AI Inference
**Severity:** LOW
**Impact:** AI fails if Modal is down

If Modal experiences an outage, AI inference fails completely. No fallback to local Ollama.

#### ISSUE-12: Single Point of Failure (Local Machine)
**Severity:** HIGH
**Impact:** Entire service down if machine fails

Everything runs on a single local Mac. If it sleeps, loses network, or crashes, the entire service is unavailable.

---

## 3. Architecture Improvements

### 3.1 Recommended Architecture

```
+------------------+     +---------------------+     +-------------------+
|  Internet User   +---->+  Cloudflare Tunnel  +---->+  launchd Services |
+------------------+     |  (Service Mode)     |     |  (macOS)          |
                         +---------------------+     +--------+----------+
                                                              |
                    +----------------------------------------+----------------------------------------+
                    |                                        |                                        |
                    v                                        v                                        v
         +----------+----------+              +--------------+-------------+           +--------------+-----------+
         |  Flask App          |              |  Ollama Proxy              |           |  Health Monitor         |
         |  (launchd)          |              |  (launchd)                 |           |  (launchd)              |
         |  Port 5151          |              |  Port 11435                |           |  Checks every 60s       |
         +----------+----------+              +--------------+-------------+           +--------------+-----------+
                    |                                        |                                        |
                    |     OLLAMA_BASE_URL                    |                                        |
                    +----------------------------------------+                                        |
                                                             |                                        |
                                                             v                                        |
                                              +--------------+-------------+                          |
                                              |  Modal T4 GPU              |                          |
                                              |  (Serverless)              |<-------------------------+
                                              |  f1-ollama-gpu             |    Warmup trigger
                                              +----------------------------+
```

### 3.2 Key Improvements

1. **Process Management with launchd**
   - All services as macOS LaunchAgents
   - Automatic restart on crash
   - Start on login
   - Proper logging

2. **Health Monitoring**
   - Periodic health checks
   - Alert on failures
   - Automatic warmup triggers

3. **Centralized Logging**
   - All logs to `/var/log/f1-telemetry/`
   - Log rotation via newsyslog

4. **Failover Strategy**
   - Optional local Ollama fallback
   - Graceful degradation

---

## 4. Implementation Plan

### Phase 1: Fix Immediate Issues (Day 1)

#### Step 1.1: Create logs directory
```bash
mkdir -p ~/Library/Logs/f1-telemetry
```

#### Step 1.2: Start missing Ollama proxy
```bash
cd /Users/will/Programming/Websites/f1-race-plots
uv run python deployment/ollama_modal_proxy.py > ~/Library/Logs/f1-telemetry/proxy.log 2>&1 &
```

#### Step 1.3: Verify AI inference works
```bash
curl -X POST http://localhost:11435/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen2.5-coder:7b", "prompt": "What is trail braking?", "stream": false}'
```

### Phase 2: Process Management (Day 2-3)

Create launchd service files for automatic management.

#### Step 2.1: Flask Application LaunchAgent

**File:** `~/Library/LaunchAgents/cc.linux-box.f1-flask.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>cc.linux-box.f1-flask</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Users/will/.local/bin/uv</string>
        <string>run</string>
        <string>python</string>
        <string>run.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/will/Programming/Websites/f1-race-plots</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PORT</key>
        <string>5151</string>
        <key>FLASK_ENV</key>
        <string>production</string>
        <key>OLLAMA_BASE_URL</key>
        <string>http://localhost:11435</string>
        <key>PATH</key>
        <string>/Users/will/.local/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>/Users/will/Library/Logs/f1-telemetry/flask.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/will/Library/Logs/f1-telemetry/flask.error.log</string>

    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
```

#### Step 2.2: Ollama Proxy LaunchAgent

**File:** `~/Library/LaunchAgents/cc.linux-box.f1-ollama-proxy.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>cc.linux-box.f1-ollama-proxy</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Users/will/.local/bin/uv</string>
        <string>run</string>
        <string>python</string>
        <string>deployment/ollama_modal_proxy.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/will/Programming/Websites/f1-race-plots</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/Users/will/.local/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>/Users/will/Library/Logs/f1-telemetry/proxy.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/will/Library/Logs/f1-telemetry/proxy.error.log</string>

    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
```

#### Step 2.3: Cloudflare Tunnel LaunchAgent

**File:** `~/Library/LaunchAgents/cc.linux-box.f1-cloudflared.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>cc.linux-box.f1-cloudflared</string>

    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/cloudflared</string>
        <string>tunnel</string>
        <string>run</string>
        <string>65a1819f-0187-41c0-b525-9b909f142ff7</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>/Users/will/Library/Logs/f1-telemetry/cloudflared.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/will/Library/Logs/f1-telemetry/cloudflared.error.log</string>

    <key>ThrottleInterval</key>
    <integer>30</integer>
</dict>
</plist>
```

#### Step 2.4: Install and Start Services
```bash
# Create log directory
mkdir -p ~/Library/Logs/f1-telemetry

# Stop existing processes
pkill -f "run.py" || true
pkill -f "ollama_modal_proxy" || true
pkill -f "cloudflared tunnel" || true

# Load services
launchctl load ~/Library/LaunchAgents/cc.linux-box.f1-ollama-proxy.plist
launchctl load ~/Library/LaunchAgents/cc.linux-box.f1-flask.plist
launchctl load ~/Library/LaunchAgents/cc.linux-box.f1-cloudflared.plist

# Verify running
launchctl list | grep f1
```

### Phase 3: Health Monitoring (Day 4)

#### Step 3.1: Health Check Script

**File:** `scripts/health-check.sh`

```bash
#!/bin/bash
# F1 Telemetry Health Check Script
# Runs periodically to verify all services are healthy

LOG_DIR="$HOME/Library/Logs/f1-telemetry"
LOG_FILE="$LOG_DIR/health.log"

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
    if curl -sf https://f1.linux-box.cc/ > /dev/null 2>&1; then
        return 0
    fi
    return 1
}

warmup_modal() {
    # Trigger Modal warmup if proxy is healthy
    curl -sf -X POST http://localhost:11435/warmup > /dev/null 2>&1
}

# Main health check
HEALTHY=true

if ! check_flask; then
    log "ERROR: Flask app not responding on port 5151"
    HEALTHY=false
fi

if ! check_proxy; then
    log "ERROR: Ollama proxy not responding on port 11435"
    HEALTHY=false
fi

if ! check_cloudflare; then
    log "WARNING: Cloudflare tunnel not responding"
fi

if [ "$HEALTHY" = true ]; then
    log "OK: All services healthy"
    # Warmup Modal to reduce cold starts
    warmup_modal
fi
```

#### Step 3.2: Health Check LaunchAgent

**File:** `~/Library/LaunchAgents/cc.linux-box.f1-health.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>cc.linux-box.f1-health</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Users/will/Programming/Websites/f1-race-plots/scripts/health-check.sh</string>
    </array>

    <key>StartInterval</key>
    <integer>300</integer>

    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
```

### Phase 4: Improved Proxy with Fallback (Day 5)

Add local Ollama fallback and warmup integration.

See `deployment/ollama_modal_proxy_improved.py` for the enhanced implementation.

---

## 5. Cost Analysis

### Current Costs

| Component | Monthly Cost | Notes |
|-----------|--------------|-------|
| Modal GPU (T4) | $0 | Within $30 free tier |
| Cloudflare Tunnel | $0 | Free tier |
| Local Infrastructure | $0 | Existing Mac |
| **Total** | **$0** | |

### Projected Costs with Improvements

| Component | Monthly Cost | Notes |
|-----------|--------------|-------|
| Modal GPU (T4) | $0-$2 | Increased warmup calls |
| Cloudflare Tunnel | $0 | Free tier |
| Local Infrastructure | $0 | Existing Mac |
| **Total** | **$0-$2** | Still within free tier |

### Cost Optimization Recommendations

1. **Reduce scaledown_window**: Current 600s (10 min) could be reduced to 300s (5 min) if traffic is predictable
2. **Batch warmup calls**: Instead of per-health-check warmup, use intelligent scheduling
3. **Monitor usage**: Track Modal usage at https://modal.com/usage

---

## 6. Performance Optimization

### Current Performance

| Metric | Current | Target |
|--------|---------|--------|
| Plot generation | 3-8s | 3-8s (no change needed) |
| AI inference (warm) | 5-10s | 5-10s (no change needed) |
| AI inference (cold) | 15-25s | <15s |
| Cold start frequency | Every 10min idle | Every 30min idle |

### Optimization Strategies

#### 6.1 Reduce Cold Start Impact

1. **Proactive Warmup**
   - Health check triggers warmup every 5 minutes
   - Keeps container warm during business hours

2. **Increase scaledown_window**
   ```python
   # In app_modal_ollama_only.py
   scaledown_window=1800,  # 30 minutes instead of 10
   ```

   **Trade-off:** Slightly higher cost (~$1-2/month more)

#### 6.2 Optimize Modal Function

```python
# Pre-warm the model on container start
@app.function(
    image=image,
    gpu="T4",
    timeout=900,
    scaledown_window=1800,  # 30 minutes
    volumes={"/root/.ollama": ollama_volume},
)
def generate(model: str, prompt: str, temperature: float = 0.1) -> dict:
    # Model is already loaded from previous inference
    # Just run inference
    ...
```

---

## 7. Security Recommendations

### 7.1 Immediate Actions

1. **Ensure .env.secret exists**
   ```bash
   if [ ! -f .env.secret ]; then
       python -c 'import secrets; print(secrets.token_hex(32))' > .env.secret
   fi
   ```

2. **Remove fallback secret key**
   ```python
   # In app/__init__.py
   import sys
   secret_key = os.getenv('FLASK_SECRET_KEY')
   if not secret_key:
       try:
           with open('.env.secret') as f:
               secret_key = f.read().strip()
       except FileNotFoundError:
           print("ERROR: No secret key found. Create .env.secret or set FLASK_SECRET_KEY")
           sys.exit(1)
   app.secret_key = secret_key
   ```

### 7.2 Network Security

The current setup is secure because:
- Cloudflare Tunnel provides TLS termination
- Flask only listens on localhost:5151 (not exposed)
- Proxy only listens on localhost:11435 (not exposed)
- Modal function requires authentication

No changes needed for network security.

### 7.3 Modal Authentication

Modal authentication is handled via `~/.modal.toml`. Ensure:
- File permissions are 600 (owner read/write only)
- Token is rotated periodically via `modal token new`

---

## 8. Disaster Recovery

### 8.1 Backup Strategy

| Asset | Backup Method | Frequency |
|-------|---------------|-----------|
| FastF1 cache | Git LFS / manual copy | Weekly |
| Configuration | Git repository | On change |
| Modal deployment | `modal deploy` from source | On change |

### 8.2 Recovery Procedures

#### Scenario: Machine Reboot
**Recovery:** Automatic (launchd services start on login)

#### Scenario: Flask App Crash
**Recovery:** Automatic (launchd KeepAlive restarts)

#### Scenario: Modal Function Down
**Recovery:**
1. Check Modal status: `modal app list`
2. Redeploy: `modal deploy deployment/app_modal_ollama_only.py`

#### Scenario: Cloudflare Tunnel Down
**Recovery:**
1. Check status: `launchctl list | grep cloudflared`
2. Restart: `launchctl kickstart -k gui/$(id -u)/cc.linux-box.f1-cloudflared`

#### Scenario: Complete Machine Failure
**Recovery:**
1. Set up new machine with macOS
2. Clone repository
3. Install dependencies: `uv pip install -r requirements.txt`
4. Install launchd services (Phase 2)
5. Configure Cloudflare tunnel with existing credentials
6. Deploy Modal function

---

## 9. Monitoring Dashboard

### 9.1 Quick Status Check

```bash
#!/bin/bash
# scripts/status.sh - Quick status overview

echo "=== F1 Telemetry Status ==="
echo ""

echo "Services:"
launchctl list | grep -E "f1-(flask|proxy|cloudflared)" | while read line; do
    if echo "$line" | grep -q "^-"; then
        echo "  [STOPPED] $(echo $line | awk '{print $3}')"
    else
        echo "  [RUNNING] $(echo $line | awk '{print $3}')"
    fi
done

echo ""
echo "Health Checks:"
curl -sf http://localhost:5151/ > /dev/null && echo "  Flask: OK" || echo "  Flask: FAILED"
curl -sf http://localhost:11435/health > /dev/null && echo "  Proxy: OK" || echo "  Proxy: FAILED"
curl -sf https://f1.linux-box.cc/ > /dev/null && echo "  Public: OK" || echo "  Public: FAILED"

echo ""
echo "Recent Logs:"
tail -3 ~/Library/Logs/f1-telemetry/health.log 2>/dev/null || echo "  No health logs yet"
```

### 9.2 Prometheus Metrics

The application already exposes Prometheus metrics at `/metrics`. Consider setting up:
- Local Prometheus server
- Grafana dashboard
- AlertManager for notifications

---

## 10. Files to Create

### Summary of New Files

| File | Purpose |
|------|---------|
| `~/Library/LaunchAgents/cc.linux-box.f1-flask.plist` | Flask service |
| `~/Library/LaunchAgents/cc.linux-box.f1-ollama-proxy.plist` | Proxy service |
| `~/Library/LaunchAgents/cc.linux-box.f1-cloudflared.plist` | Tunnel service |
| `~/Library/LaunchAgents/cc.linux-box.f1-health.plist` | Health monitor |
| `scripts/health-check.sh` | Health check script |
| `scripts/status.sh` | Status dashboard |
| `scripts/install-services.sh` | Service installer |

---

## 11. Conclusion

The hybrid architecture is the correct choice for this application. The main issues are operational (process management, monitoring) rather than architectural.

**Priority Fixes:**
1. **CRITICAL:** Start the Ollama proxy (currently not running)
2. **HIGH:** Implement launchd services for automatic restart
3. **MEDIUM:** Add health monitoring and warmup
4. **LOW:** Implement local Ollama fallback

**Total Implementation Time:** 4-5 days
**Monthly Cost Impact:** $0 (stays within free tier)
**Reliability Improvement:** Significant (from manual to fully automated)

---

## Appendix A: Quick Reference Commands

```bash
# Start all services manually
./scripts/start-production-gpu.sh

# Check service status
launchctl list | grep f1

# View logs
tail -f ~/Library/Logs/f1-telemetry/flask.log
tail -f ~/Library/Logs/f1-telemetry/proxy.log
tail -f ~/Library/Logs/f1-telemetry/health.log

# Restart a service
launchctl kickstart -k gui/$(id -u)/cc.linux-box.f1-flask
launchctl kickstart -k gui/$(id -u)/cc.linux-box.f1-ollama-proxy
launchctl kickstart -k gui/$(id -u)/cc.linux-box.f1-cloudflared

# Stop all services
launchctl unload ~/Library/LaunchAgents/cc.linux-box.f1-*.plist

# Deploy Modal function
modal deploy deployment/app_modal_ollama_only.py

# Check Modal logs
modal app logs f1-ollama-gpu
```

---

**Document Version:** 1.0
**Last Updated:** January 8, 2026

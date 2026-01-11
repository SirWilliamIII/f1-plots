# F1 Telemetry App - Development Log

## 2026-01-11: Beam GPU Deployment Working

### Summary
Successfully deployed F1 telemetry app with hybrid Oracle/Beam.cloud architecture. All CPU work (Flask, FastF1, caching) runs on Oracle server, GPU inference (Ollama) runs on Beam A10G GPU.

### Architecture
```
Internet → f1.linux-box.cc (Cloudflare Tunnel)
  ↓
Flask App (Oracle server, port 5151)
  ↓
Beam Proxy (Oracle server, port 11435)
  ↓
Beam GPU Endpoint (A10G GPU in cloud)
  - Model: qwen2.5-coder:7b (pre-downloaded in image)
  - Deployment: v6
```

### Key Issues Fixed

1. **Model Pull Failure on Beam**
   - Problem: `ollama pull` was failing during runtime with exit code 1
   - Root cause: Model download progress output to stderr was being treated as error
   - Solution: Pre-downloaded model into Beam image during build

2. **Volume Overwriting Baked Model**
   - Problem: Persistent volume at `/root/.ollama` was overwriting pre-downloaded model
   - Solution: Removed volume mount since model is baked into image

3. **Proxy Timeout Issues**
   - Problem: 3-minute timeout too short for cold starts
   - Solution: Increased timeout to 12 minutes (720 seconds)

4. **Cloudflare Tunnel Configuration**
   - Problem: HTTP 522 errors, tunnel running with token but not configured
   - Solution: Configured oracle-tunnel (594670bf-88c2-4e8c-8a8e-f41aa32142be) to route f1.linux-box.cc → http://localhost:5151

### Deployment Details

**Beam Deployment (v6):**
- Endpoint: `https://f1-ollama-b942c80-v6.app.beam.cloud`
- GPU: A10G
- Memory: 16Gi
- CPU: 2 cores
- Keep-alive: 600 seconds (10 minutes)
- Timeout: 900 seconds (15 minutes)
- Model: qwen2.5-coder:7b (baked into image)

**Files Modified:**
- `deployment/app_beam_ollama.py` - Beam GPU endpoint
  - Pre-download model during image build
  - Removed volume mount
  - Improved error handling and logging
- `deployment/ollama_beam_proxy.py` - Local proxy on Oracle
  - Increased timeout to 720 seconds

**Running Services:**
```bash
# Flask app
uv run run.py  # Port 5151

# Beam proxy
BEAM_ENDPOINT_URL=https://f1-ollama-b942c80-v6.app.beam.cloud uv run python deployment/ollama_beam_proxy.py  # Port 11435

# Cloudflare tunnel (systemd)
sudo systemctl status cloudflared  # oracle-tunnel
```

### Performance
- **Cold start**: ~4 minutes (first request after idle)
- **Warm requests**: ~5-10 seconds (model already loaded)
- **Container stays warm**: 10 minutes after last request

### Testing
```bash
# Test Flask → Proxy → Beam pipeline
curl -X POST http://localhost:5151/ollama_proxy/generate \
  -H 'Content-Type: application/json' \
  -d '{"model": "qwen2.5-coder:7b", "prompt": "What is DRS in F1?", "stream": false}'

# Expected response time: 3-5 seconds (warm), 230+ seconds (cold start)
```

### Access
- **Local:** http://localhost:5151
- **Public:** https://f1.linux-box.cc (via Cloudflare tunnel)

### Next Steps
- Monitor Beam costs and performance
- Consider implementing request queuing for cold starts
- Add health check endpoints
- Set up monitoring/alerting for tunnel status

---

## System Status: ✅ OPERATIONAL

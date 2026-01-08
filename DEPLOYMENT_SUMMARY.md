# F1 Telemetry Deployment Summary

## Quick Reference

### ✅ Production Deployment (Working)

**Hybrid GPU Architecture** - https://f1.linux-box.cc

```bash
# Start production with GPU acceleration
./scripts/start-production-gpu.sh
```

**Architecture:**
```
User → Cloudflare Tunnel → Local Flask (port 5151) → Modal T4 GPU
                                ↓
                          FastF1 Cache (local)
```

**Performance:**
- Homepage: <1s
- Plot generation: 3-8s
- AI analysis: 5-10s (GPU) 🚀
- Cost: $0/month

**Status:** ✅ Production-ready, fully functional

---

### ⚠️ Modal Full Deployment (Not Working)

https://sirwilliamiii--f1-telemetry-web.modal.run/

**Status:** ❌ Not functional - plot generation times out

**What Works:**
- ✅ Homepage (1.2s)
- ✅ API endpoints

**What Doesn't Work:**
- ❌ Plot generation (60s timeout)
- ❌ Full user flow

**Root Cause:** Modal HTTP gateway has hardcoded ~60s timeout, can't handle long-running requests (FastF1 downloads + plot generation = 60-120s).

**Conclusion:** Modal full deployment is fundamentally incompatible with this application. Not fixable with configuration.

---

## Deployment Commands

### Current Production (Hybrid)

```bash
# 1. Deploy Ollama GPU to Modal (one-time)
modal deploy deployment/app_modal_ollama_only.py

# 2. Start local proxy (background)
uv run python deployment/ollama_modal_proxy.py &

# 3. Start Flask with GPU
export OLLAMA_BASE_URL=http://localhost:11435
./scripts/start-production-gpu.sh

# 4. Start Cloudflare Tunnel (if not running)
cloudflared tunnel run 65a1819f-0187-41c0-b525-9b909f142ff7 &

# Access at: https://f1.linux-box.cc
```

### Development (Local CPU)

```bash
./scripts/dev-start.sh
# Access at: http://localhost:5050
```

### Modal GPU Only (Working - for AI inference)

```bash
modal deploy deployment/app_modal_ollama_only.py
# Used by hybrid architecture for GPU inference
```

### Modal Full App (Not Working - reference only)

```bash
modal deploy deployment/app_modal_fixed.py
# Homepage works but plot generation fails
# https://sirwilliamiii--f1-telemetry-web.modal.run/
```

---

## Comparison

| Feature | Hybrid (Production) | Modal Full | Local Dev |
|---------|---------------------|-----------|-----------|
| **Plot Generation** | ✅ 3-8s | ❌ Timeout | ✅ 3-8s |
| **AI Inference** | ✅ 5-10s (GPU) | N/A | ⏳ 30-60s (CPU) |
| **Public Access** | ✅ f1.linux-box.cc | ⚠️ modal.run | ❌ localhost |
| **Cost** | $0/month | $0/month | $0/month |
| **Reliability** | ✅ Stable | ❌ Broken | ✅ Stable |
| **Setup Time** | 5 min | 1 min | Instant |
| **Recommendation** | ⭐ **USE THIS** | ❌ Don't use | Dev only |

---

## Files

### Production Files
- `scripts/start-production-gpu.sh` - Start production with GPU
- `deployment/ollama_modal_proxy.py` - Local proxy to Modal GPU
- `deployment/app_modal_ollama_only.py` - Modal GPU function

### Reference/Testing Files
- `deployment/app_modal_fixed.py` - Optimized Modal full deployment (still broken)
- `deployment/app_modal.py` - Original Modal deployment
- `MODAL_DEPLOYMENT_FIX.md` - Detailed analysis of Modal issues

### Documentation
- `CLAUDE.md` - Main project documentation
- `DEPLOYMENT_SUMMARY.md` - This file
- `PROJECT_STRUCTURE.md` - Codebase architecture

---

## Key Learnings

1. **Modal is excellent for:** GPU inference, short API requests, background jobs
2. **Modal is NOT suitable for:** Long HTTP requests (>60s), data-heavy operations, multi-step pipelines
3. **Best practice:** Use Modal as specialized GPU backend, not full application platform
4. **Hybrid architecture:** Best of both worlds - local reliability + cloud GPU acceleration

---

**Last Updated:** January 8, 2026
**Status:** Hybrid deployment production-ready ✅
**Modal Full Deployment:** Not recommended ❌

# Hybrid Deployment: Local Flask + Modal GPU

This setup gives you the **best of both worlds**:
- ✅ Flask and FastF1 run locally (no download timeouts)
- ✅ Ollama runs on Modal T4 GPU (10x faster inference)
- ✅ $0/month cost (within free tier)
- ✅ No cold starts for plot generation

## Architecture

```
User → Local Flask (port 5050/5151)
         ↓
      FastF1 (local cache, fast)
         ↓
      Plot Generation (local, no cold start)
         ↓
      Ollama Modal Proxy (port 11435)
         ↓
      Modal T4 GPU Function (5-10s inference)
```

## Setup (5 minutes)

### Step 1: Deploy Ollama GPU Function to Modal

```bash
# Deploy the simplified Ollama-only function
modal deploy app_modal_ollama_only.py
```

**Expected output:**
```
✓ Created generate => https://your-username--f1-ollama-gpu-generate.modal.run
✅ App deployed!
```

This takes 2-3 minutes for first deployment (building container, installing Ollama).

### Step 2: Start the Local Ollama Proxy

In a new terminal:
```bash
# This proxy forwards Ollama requests to Modal GPU
python ollama_modal_proxy.py
```

**Expected output:**
```
🚀 Starting Ollama → Modal GPU Proxy
📍 Listening on: http://localhost:11435
🔗 Forwarding to: Modal T4 GPU function
```

Keep this running in the background.

### Step 3: Start Flask with the Proxy

In another terminal:
```bash
# Point Flask to the Modal proxy instead of local Ollama
export OLLAMA_BASE_URL=http://localhost:11435
./dev-start.sh
```

**That's it!** Your app now uses GPU-accelerated AI while keeping everything else local.

## Testing

1. **Visit http://localhost:5050**
2. **Generate a plot** (Monaco 2024, Qualifying, Verstappen vs Hamilton)
   - Should take 3-8 seconds (normal, no cold start)
3. **Click on a moment** to trigger AI analysis
   - First request: 15-20 seconds (Modal cold start + model pull)
   - Subsequent requests: **5-10 seconds** ✨ (10x faster than local CPU!)

## Performance Comparison

| Operation | Local (CPU) | Hybrid (GPU) |
|-----------|-------------|--------------|
| Plot Generation | 3-8s | 3-8s (same) |
| **AI Analysis (first)** | 30-60s | 15-20s |
| **AI Analysis (warm)** | 30-60s | **5-10s** ⚡ |
| FastF1 Downloads | Fast (local cache) | Fast (local cache) |

## Production Deployment

For your production setup (port 5151):

```bash
# Terminal 1: Keep proxy running
python ollama_modal_proxy.py

# Terminal 2: Start production Flask
export OLLAMA_BASE_URL=http://localhost:11435
./prod-restart.sh
```

Your Cloudflare tunnel stays pointed at `localhost:5151`, no changes needed!

## Cost Breakdown (15 queries/month)

| Component | Cost |
|-----------|------|
| Modal GPU inference (15 × 10s) | $0.025 |
| Cold starts (5 × 15s) | $0.012 |
| **Total** | **$0.037/month** |
| **After $30 free tier** | **$0.00** ✅ |

## Troubleshooting

**Problem: "Failed to connect to Modal GPU function"**
```bash
# Check Modal app is deployed
modal app list

# Should show:
# f1-ollama-gpu | deployed
```

**Problem: "Streaming not supported"**
- The Modal proxy doesn't support streaming (not needed for your use case)
- If needed, add streaming support by modifying the proxy

**Problem: Proxy connection refused**
```bash
# Check proxy is running
curl http://localhost:11435/health

# Should return: {"status": "healthy", "backend": "modal-gpu"}
```

## Rolling Back

To go back to local Ollama:

```bash
# Stop the proxy (Ctrl+C)

# Use local Ollama
export OLLAMA_BASE_URL=http://localhost:11434
./dev-start.sh
```

## Benefits of This Approach

1. **No FastF1 timeout issues** - Data stays on fast local disk
2. **10x faster AI** - GPU vs CPU for Ollama
3. **No plot generation cold starts** - Flask runs locally
4. **$0 cost** - Tiny GPU usage within free tier
5. **Easy rollback** - Just stop the proxy
6. **Simple architecture** - No complex Modal ASGI setup

## Next Steps

1. Monitor Modal usage: https://modal.com/usage (should be ~$0)
2. Check proxy logs for errors
3. Enjoy 10x faster AI analysis! 🚀

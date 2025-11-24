# F1 Telemetry App - Modal Deployment Guide

This guide walks you through deploying your F1 telemetry application to Modal's serverless GPU platform.

## Prerequisites

1. **Modal Account**
   - Sign up at [modal.com](https://modal.com)
   - Get $30/month free credits (covers your entire usage!)

2. **Modal CLI**
   ```bash
   pip install modal
   modal setup  # Authenticate with your Modal account
   ```

3. **Existing Components**
   - 2.3GB FastF1 cache (optional, will rebuild if needed)
   - Ollama models: `f1-analyst:latest` (or will pull automatically)

---

## Cost Estimate

For **10-20 queries/month**:

| Component | Cost/Month |
|-----------|------------|
| GPU inference (T4) | $0.04 |
| Flask app CPU | $0.01 |
| Storage (8GB) | $0.80 |
| **Total** | **$0.85** |
| **After free tier** | **$0.00** ✅ |

Modal provides $30/month free credits, so your app runs **completely free** for months/years!

---

## Deployment Steps

### Step 1: Upload FastF1 Cache (Optional but Recommended)

This step is optional but recommended to avoid re-downloading F1 data. If skipped, the cache will rebuild automatically on first use.

```bash
# Create Modal volume
modal volume create f1-data

# Upload your existing cache (saves ~10 minutes on first run)
modal volume put f1-data fastf1_cache /fastf1_cache

# Verify upload
modal volume ls f1-data /fastf1_cache
```

**Expected output:**
```
✓ Created volume f1-data
✓ Uploaded 2.3GB in 487 files
✓ Volume ready at /fastf1_cache
```

---

### Step 2: Deploy Ollama Model

Upload your custom `f1-analyst` Ollama model to Modal:

```bash
# Export your local Ollama model
ollama pull f1-analyst:latest  # Ensure model exists locally

# Create a Modelfile if needed (already exists in your repo)
# The model will be built within Modal from the Modelfile

# Deploy to Modal (model will be pulled/created on first run)
modal run app_modal.py
```

**Note:** The first run will take 2-3 minutes to pull the base model and create `f1-analyst`. Subsequent runs use the cached model.

---

### Step 3: Deploy Flask Application

```bash
# Deploy the entire application to Modal
modal deploy app_modal.py
```

**Expected output:**
```
✓ Created objects.
├── 🔨 Created mount /Users/will/Programming/Websites/f1-race-plots
├── 🔨 Created volume f1-data
├── 🔨 Created run_ollama_inference => https://your-username--f1-telemetry-run-ollama-inference.modal.run
├── 🔨 Created run_ollama_generate => https://your-username--f1-telemetry-run-ollama-generate.modal.run
├── 🔨 Created flask_app => https://your-username--f1-telemetry-flask-app.modal.run
└── 🔨 Created warm_cache (scheduled)

✅ App deployed! View at https://modal.com/apps/your-username/f1-telemetry
```

**Your app is now live at the Flask URL!** 🎉

---

### Step 4: Update DNS (Optional)

You have two options for accessing your app:

**Option A: Use Modal URL directly**
```
https://your-username--f1-telemetry-flask-app.modal.run
```

**Option B: Keep Cloudflare Tunnel (recommended)**

Update your Cloudflare tunnel config to point to the Modal URL:

```yaml
# ~/.cloudflared/config.yaml
tunnel: <your-tunnel-id>
credentials-file: /Users/will/.cloudflared/<uuid>.json

ingress:
  - hostname: f1.linux-box.cc
    service: https://your-username--f1-telemetry-flask-app.modal.run
  - service: http_status:404
```

Restart the tunnel:
```bash
launchctl stop com.f1app.cloudflared-tunnel
launchctl start com.f1app.cloudflared-tunnel
```

Your site remains at `https://f1.linux-box.cc` but is now powered by Modal!

---

## Testing Your Deployment

### 1. Test Flask App
```bash
# Get your Modal Flask URL from deployment output
curl https://your-username--f1-telemetry-flask-app.modal.run/health

# Expected response:
{"status": "healthy", "cache_size": 0, "deployment": "modal"}
```

### 2. Test Plot Generation
Visit your Modal URL in a browser and generate a plot:
1. Select year, race, session
2. Pick two drivers
3. Click "Compare Fastest Laps"

**Expected response time:**
- First request (cold start): 20-30 seconds
- Subsequent requests: 5-15 seconds

### 3. Test AI Analysis
Click on any moment annotation to trigger Ollama inference:

**Expected response time:**
- First request (cold start): 15-20 seconds
- Subsequent requests: 5-10 seconds

### 4. Monitor Usage
```bash
# View logs
modal app logs f1-telemetry

# Check costs
# Visit https://modal.com/usage to see your spending (should be $0!)
```

---

## Environment Variables

Your app reads these from the environment:

| Variable | Default | Description |
|----------|---------|-------------|
| `MODAL_DEPLOYMENT` | `false` | Set to `true` when deployed to Modal (auto-set) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama URL (auto-configured for Modal) |
| `FASTF1_CACHE` | `fastf1_cache/` | Cache directory (auto-set to `/cache/fastf1_cache` on Modal) |

**No manual environment variables needed!** The app auto-detects Modal deployment.

---

## Updating Your Deployment

When you make code changes:

```bash
# Redeploy (takes ~30 seconds)
modal deploy app_modal.py

# Or use watch mode during development
modal serve app_modal.py  # Auto-redeploys on file changes
```

**No downtime!** Modal performs rolling updates.

---

## Monitoring & Debugging

### View Logs
```bash
# Real-time logs
modal app logs f1-telemetry --follow

# Filter by function
modal app logs f1-telemetry --function flask_app
modal app logs f1-telemetry --function run_ollama_inference
```

### Check Volume Contents
```bash
# List FastF1 cache
modal volume ls f1-data /fastf1_cache

# Check cache size
modal volume ls f1-data /fastf1_cache --recursive | wc -l
```

### Monitor Costs
Visit [modal.com/usage](https://modal.com/usage) to see:
- GPU seconds used
- Storage costs
- Total spending (should stay at $0 with free tier!)

### Common Issues

**Issue: Cold starts taking 30+ seconds**
- **Cause:** Ollama model loading on first request
- **Solution:** Enable `keep_warm=1` in `app_modal.py` (costs ~$5/month but eliminates cold starts)

```python
@app.function(
    gpu="T4",
    keep_warm=1,  # Keep 1 GPU instance warm
)
```

**Issue: "Volume not found" error**
- **Cause:** Volume not created
- **Solution:** `modal volume create f1-data`

**Issue: FastF1 data not loading**
- **Cause:** Cache path incorrect or volume not mounted
- **Solution:** Check `SESSION_CONFIG.cache_directory` matches Modal volume mount point

**Issue: Ollama model not found**
- **Cause:** Model not pulled/created in Modal container
- **Solution:** Check `run_ollama_inference` function logs, model will auto-pull on first run

---

## Scaling & Performance

### Cache Warming (Recommended)

The deployment includes a daily cache warming job that preloads popular sessions:

```python
@app.function(schedule=modal.Cron("0 0 * * *"))  # Daily at midnight
def warm_cache():
    # Preloads Monaco, British GP, etc.
    pass
```

This runs automatically every night, ensuring frequently requested data is cached.

### Keep Warm Instances (Optional)

To eliminate cold starts entirely, enable keep-warm:

```python
# In app_modal.py, modify flask_app:
@app.function(
    keep_warm=1,  # Keep 1 instance always warm
)
```

**Cost impact:** ~$5-10/month (still within free tier for most use cases)

### GPU Upgrade (Optional)

If T4 is too slow, upgrade to faster GPU:

```python
# In app_modal.py, change:
gpu="T4"  # $0.000164/sec
# to:
gpu="A10"  # $0.000306/sec (faster inference)
```

---

## Rollback to Local Deployment

If you need to rollback:

1. **Stop using Modal:**
   ```bash
   export MODAL_DEPLOYMENT=false
   ```

2. **Start local services:**
   ```bash
   ./dev-start.sh  # Development
   # or
   ./prod-restart.sh  # Production
   ```

3. **Update Cloudflare tunnel** to point back to `localhost:5151`

**Your local deployment continues to work alongside Modal!** No code removal needed.

---

## FAQ

**Q: Can I use this with my existing Cloudflare tunnel?**
A: Yes! Just update your tunnel config to proxy to the Modal URL instead of localhost.

**Q: What happens if I exceed the free tier?**
A: Modal will email you. Set up a budget alert at [modal.com/usage](https://modal.com/usage) to avoid surprises.

**Q: Can I use a different GPU?**
A: Yes! Edit `app_modal.py` and change `gpu="T4"` to `gpu="A10"`, `gpu="L4"`, or `gpu="A100"`.

**Q: How do I add more Ollama models?**
A: Upload additional models using `ollama pull <model>` and they'll be available in Modal.

**Q: Is my data secure?**
A: Yes! Modal volumes are private to your account. Only your functions can access them.

**Q: Can I deploy to multiple environments (dev/prod)?**
A: Yes! Create separate Modal apps:
```python
app = modal.App("f1-telemetry-dev")  # Development
app = modal.App("f1-telemetry-prod")  # Production
```

---

## Cost Optimization Tips

1. **Use cache warming** to preload popular sessions (reduces user wait times, no extra cost)
2. **Don't enable keep_warm** unless you need sub-second response times (saves $5-10/month)
3. **Use T4 GPU** instead of A10/A100 (80% cheaper, sufficient for your use case)
4. **Monitor free tier usage** monthly at [modal.com/usage](https://modal.com/usage)

---

## Support

- **Modal docs:** [modal.com/docs](https://modal.com/docs)
- **Modal Slack:** [modal-community.slack.com](https://modal-community.slack.com)
- **Modal examples:** [github.com/modal-labs/modal-examples](https://github.com/modal-labs/modal-examples)

---

## Summary

You've successfully deployed your F1 telemetry app to Modal! 🎉

**What you get:**
- ✅ Serverless GPU inference (T4)
- ✅ Auto-scaling from 0 to infinity
- ✅ $0/month cost (within free tier)
- ✅ Sub-20 second response times
- ✅ No infrastructure management
- ✅ Persistent FastF1 cache
- ✅ Daily cache warming

**Next steps:**
1. Monitor your deployment at [modal.com/apps](https://modal.com/apps)
2. Test all features (plots, AI analysis)
3. Update your DNS/Cloudflare tunnel
4. Share your site: `https://f1.linux-box.cc` (or Modal URL)

Enjoy your cloud-powered F1 analysis platform! 🏎️💨

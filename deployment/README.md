# Deployment Configurations

This directory contains deployment-specific files for various platforms.

## Files

### Modal Serverless Deployments
- **`app_modal.py`** - Full Modal deployment (Flask + Ollama on GPU)
  - Complete serverless deployment
  - Includes web server and GPU inference
  - Deploy with: `modal deploy deployment/app_modal.py`

- **`app_modal_ollama_only.py`** - GPU-only Modal deployment
  - Only Ollama inference on T4 GPU
  - Use with local Flask + hybrid architecture
  - Deploy with: `modal deploy deployment/app_modal_ollama_only.py`

### Hybrid GPU Proxy
- **`ollama_modal_proxy.py`** - Local proxy server for Modal GPU
  - Runs locally on port 11435
  - Forwards Ollama requests to Modal T4 GPU
  - Run with: `python deployment/ollama_modal_proxy.py`
  - Use with: `export OLLAMA_BASE_URL=http://localhost:11435`

## Usage

### Full Modal Deployment
```bash
cd /path/to/project
modal deploy deployment/app_modal.py
```

### Hybrid GPU Architecture (Recommended)
```bash
# 1. Deploy GPU function to Modal
modal deploy deployment/app_modal_ollama_only.py

# 2. Run local proxy (in background)
python deployment/ollama_modal_proxy.py &

# 3. Start Flask with GPU proxy
export OLLAMA_BASE_URL=http://localhost:11435
python run.py
```

See `/docs` for detailed deployment guides.

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Flask-based F1 telemetry visualization application** that generates detailed comparison plots between two drivers' performance data. The application integrates with **Ollama AI** for intelligent telemetry analysis and uses **FastF1** for accessing Formula 1 data.

## Core Architecture

### Main Components

- **`app.py`**: Main Flask application with telemetry comparison endpoints
- **`session_manager.py`**: Thread-safe F1 session caching system with preloading
- **`utils.py`**: Racing technique classification and telemetry context extraction
- **`config.py`**: Centralized configuration management for all components
- **`validators.py`**: Input validation for security (prevents injection attacks)
- **`ollama_client.py`**: Unified Ollama client for local and Modal deployments
- **`ollama_modal_proxy.py`**: Local proxy forwarding Ollama requests to Modal GPU
- **`app_modal_ollama_only.py`**: Simplified Modal GPU function (Ollama only)
- **`app_modal.py`**: Full Modal deployment wrapper (reference implementation)
- **`start-production-gpu.sh`**: Production startup script with GPU acceleration

### Key Features

- **5-panel telemetry plots**: Throttle, Brake, RPM, Speed, and Gear comparison
- **AI-powered analysis**: Contextual telemetry insights via Ollama integration
- **Hybrid GPU Architecture**: Local Flask/FastF1 + Modal T4 GPU for 5x faster AI (5-10s vs 30-60s)
- **Enhanced AI formatting**: Styled markdown with auto-highlighted driver names, times, speeds
- **Performance caching**: Background preloading of popular F1 sessions
- **Moment classification**: Automatic identification of racing techniques (trail braking, gear selection, etc.)
- **Prometheus metrics**: Built-in performance monitoring
- **Input validation**: Security hardening against injection attacks
- **Multi-deployment support**: Local (CPU), Hybrid (GPU proxy), Docker, and Modal (full serverless)

## Development Commands

### Prerequisites
```bash
# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify uv installation
uv --version
```

### Local Development
```bash
# Install dependencies
uv pip install -r requirements.txt

# Run development server (port 5050)
./dev-start.sh
# OR manually:
export FLASK_ENV=development && export PORT=5050 && uv run python app.py

# Run with production server
uv run gunicorn app:app -c gunicorn.conf.py
```

### Ollama Model Management
```bash
# Create the specialized F1 models (required for AI analysis)
ollama create f1expert -f f1expert.modelfile
ollama create f1-analyst -f f1-analyst.modelfile

# Verify models are available
ollama list | grep f1

# Pull base model (if needed)
ollama pull qwen2.5-coder:7b
```

### Docker Development
```bash
# Build and run
docker build -t f1-race-plots .
docker run -p 8080:8080 f1-race-plots

# Using docker-compose
docker-compose up -d

# Using Podman
./deploy-podman.sh
```

### Modal Deployment (Serverless GPU)
```bash
# Install Modal CLI
pip install modal
modal setup  # Authenticate

# Deploy to Modal (serverless GPU platform)
./deploy-modal.sh

# Development mode (auto-reload)
./deploy-modal.sh --dev

# Skip cache upload (faster deployment)
./deploy-modal.sh --no-cache

# View logs
modal app logs f1-telemetry

# Check costs (should be $0 within free tier)
# Visit: https://modal.com/usage
```

**Modal Benefits:**
- $0/month hosting (within $30 free tier)
- Serverless T4 GPU for 10x faster AI inference
- Auto-scaling from 0 to infinity
- No infrastructure management
- See [DEPLOY_MODAL.md](DEPLOY_MODAL.md) for details

### Hybrid GPU Architecture (Recommended)

**Best of both worlds**: Local Flask/FastF1 + Modal T4 GPU for AI inference only.

```bash
# Step 1: Deploy Ollama GPU function to Modal
modal deploy app_modal_ollama_only.py

# Step 2: Start the local Ollama proxy (in background)
uv run python ollama_modal_proxy.py &

# Step 3: Start Flask with GPU proxy
export OLLAMA_BASE_URL=http://localhost:11435
./start-production-gpu.sh
```

**Architecture:**
```
User → Flask (localhost:5151) → Ollama Proxy (localhost:11435) → Modal T4 GPU
        ↓                         ↓
   FastF1 (local cache)      Modal Function (GPU inference)
```

**Benefits:**
- ✅ 5x faster AI inference (30-60s → 5-10s)
- ✅ $0/month cost (within Modal $30 free tier)
- ✅ No FastF1 timeout issues (data stays local)
- ✅ No plot generation cold starts (Flask runs locally)
- ✅ Easy rollback (just stop proxy)

**Performance:**
- Plot generation: 3-8s (same as local)
- AI analysis (first): 15-20s (Modal cold start + model build)
- AI analysis (warm): **5-10s** ⚡ (5x faster than local CPU!)

**Local Ollama is NOT required!** The proxy uses Modal's Python SDK to call the cloud GPU function. You can uninstall local Ollama completely.

### Testing & Debugging
```bash
# Check cache statistics (adjust port based on environment)
curl http://localhost:5050/cache_stats  # Development
curl http://localhost:5151/cache_stats  # Production

# Clear session cache
curl -X POST http://localhost:5050/clear_cache  # Development
curl -X POST http://localhost:5151/clear_cache  # Production

# Health check
curl http://localhost:5050/health  # Development
curl http://localhost:5151/health  # Production

# Prometheus metrics
curl http://localhost:5050/metrics  # Development
curl http://localhost:5151/metrics  # Production
```

## Key Implementation Details

## AI Model Architecture & Philosophy

### Core Insight: "Pattern Explainers, Not Calculators"
The F1 analyst models are designed to **interpret pre-calculated metrics** rather than compute them. This fundamental principle drives the entire architecture:

- **Telemetry Processor** (Python/FastF1): Calculates precise metrics
- **Pattern Detector** (utils.py): Identifies racing techniques
- **LLM Narrator** (Ollama models): Explains what the patterns mean

### Modelfile Design Decisions

#### F1-Analyst Model Configuration
- **Base Model**: qwen2.5-coder:7b
- **System Prompt**: ~3000 tokens (includes driver mappings, track corners, analysis framework)
- **Temperature**: 0.4 (balanced creativity/accuracy for narrative generation)
- **Context Window**: 8192 tokens
- **Philosophy**: Transform data into racing narratives that reveal the artistry behind the numbers

#### Key Modelfile Components
1. **Driver Abbreviation Mapping**: Prevents hallucinated driver names
2. **Track Corner References**: Adds atmospheric detail (e.g., "Casino Square" vs "Turn 5")
3. **Context Window Analysis**: Always examines -3 to +3 seconds around each moment
4. **Five-Plot Framework**: Systematic analysis of Throttle, Brakes, RPM, Speed, and Gear
5. **Narrative Arc Structure**: Setup → Approach → Technique → Outcome → Implication

### Optimal Prompt Engineering

#### Pattern Library for Racing Techniques
```python
RACING_PATTERNS = {
    'late_braking': "Pressure or opportunity?",
    'early_throttle': "Confidence in rear grip",
    'rpm_drop': "Traction control intervention",
    'gear_hold': "Managing deployment",
    'speed_scrub': "Setup issue or mistake?",
    'throttle_feather': "On the edge of adhesion"
}

### Session Management (`session_manager.py`)
- Uses `ThreadPoolExecutor` for concurrent session loading
- Implements LRU cache with configurable size (default: 50 sessions)
- Preloads popular sessions (Monaco, British GP) for faster response times
- Thread-safe with proper locking mechanisms

### Plot Generation (`app.py:602-1217`)
- Generates 5-panel matplotlib plots with custom styling
- Automatically detects and annotates key racing moments
- Includes sector markers, turn numbers, and gear change visualization
- Saves plots to BytesIO buffer for immediate serving

### AI Integration (`app.py:126-252`)
- Proxies requests to Ollama with injected telemetry context
- Uses custom Qwen2.5-coder:7b models for analysis
- Specialized model: `f1expert.modelfile` and `f1-analyst.modelfile`
- Includes comprehensive telemetry data in prompts with driver mappings
- Supports both streaming and non-streaming responses
- Temperature optimized for speed (0.2-0.3) with focused context window

### AI Response Formatting (`templates/result.html`)
JavaScript function `formatF1Response()` provides professional F1 broadcast styling:

**Markdown Rendering:**
- `#` → Red H1 titles (#ff3333, uppercase, underline)
- `###` or `##` → Bright blue H3 headers (#3b9fff, left accent border)
- `**text**` → Cyan bold text (#4ecdc4)
- Lists properly wrapped in `<ul>` tags

**Auto-Detection & Highlighting:**
- **Driver names** (VER, HAM, etc.) → Golden yellow (#ffdd57) with glow effect
- **Times** (1:23.456, 23.5s) → Green monospace (#4ade80)
- **Speeds** (315 km/h) → Green monospace
- **RPM values** (12,500 RPM) → Green monospace
- **Percentages** (100%) → Green monospace

**Smart Context Detection:**
Uses driver abbreviations from template context to intelligently highlight names throughout the response without false positives.

### Ollama Client Abstraction (`ollama_client.py`)
- Unified interface for local and Modal deployments
- Auto-detects deployment mode via `MODAL_DEPLOYMENT` environment variable
- Automatic fallback to local Ollama if Modal unavailable
- Health checks and model listing
- Singleton pattern for efficient connection reuse

### Input Validation (`validators.py`)
- Validates all user inputs to prevent injection attacks
- Functions: `validate_year()`, `validate_driver()`, `validate_session_type()`, `validate_race_name()`, `validate_moment_id()`
- Returns 400 Bad Request with descriptive errors
- Prevents dangerous characters in race names
- Enforces reasonable bounds on all inputs

### Moment Classification (`utils.py:1-168`)
- Analyzes telemetry data to identify racing techniques
- Differentiates between qualifying and race scenarios
- Detects: trail braking, gear selection, throttle application, overtakes, etc.
- Provides contextual descriptions for plot annotations

## Environment Configuration

### Required Environment Variables
```bash
OLLAMA_BASE_URL=http://ollama:11434        # Local Ollama (CPU)
OLLAMA_BASE_URL=http://localhost:11435     # Hybrid GPU via proxy (recommended)
FLASK_ENV=development|production           # Environment mode
PORT=8080                                  # Application port (5050 dev, 5151 prod)
MODAL_DEPLOYMENT=false|true                # Enable Modal deployment mode (auto-set by app_modal.py)
```

**For Hybrid GPU Architecture:**
```bash
# .env file
OLLAMA_BASE_URL=http://localhost:11435

# Or set in shell
export OLLAMA_BASE_URL=http://localhost:11435
```

### Secret Management
```bash
# Generate secret key (do this once)
python -c 'import secrets; print(secrets.token_hex(32))' > .env.secret

# The app reads from .env.secret file (git-ignored)
# Fallback to FLASK_SECRET_KEY environment variable
```

### Configuration Files
- **`config.py`**: Tunable parameters for session management, Flask, and Gunicorn
- **`requirements.txt`**: Python dependencies (use with `uv pip install`)
- **`requirements-minimal.txt`**: Minimal dependencies for Docker builds
- **`pyproject.toml`**: Project metadata and uv configuration
- **`uv.lock`**: Locked dependency versions for reproducible builds

## Data Flow

1. **User Request**: Select year/race/session/drivers via web interface
2. **Input Validation**: All inputs validated via `validators.py` before processing
3. **Session Loading**: SessionManager checks cache or loads from FastF1
4. **Telemetry Processing**: Extract and process driver telemetry data
5. **Plot Generation**: Create 5-panel comparison with moment annotations
6. **AI Analysis**: Generate contextual insights using Ollama (via `ollama_client.py`)
7. **Response**: Serve plot and analysis to user

### Deployment-Specific Flow

**Local Deployment (CPU):**
```
User → Flask (port 5050/5151) → Local Ollama (CPU) → FastF1 Cache (disk)
```

**Hybrid GPU Architecture (Recommended):**
```
User → Flask (local) → Ollama Proxy (port 11435) → Modal T4 GPU Function
         ↓                                            ↓
    FastF1 Cache (local disk)                    Ollama on GPU (5-10s)
```
- Flask and data operations stay local (no timeouts)
- Only AI inference goes to Modal GPU (5x speedup)
- Proxy uses Modal Python SDK (no local Ollama needed)

**Modal Full Deployment:**
```
User → Modal Flask (ASGI) → Modal GPU Function (T4) → Ollama on GPU → FastF1 Cache (Modal volume)
```

The `ollama_client.py` automatically detects which flow to use based on the `MODAL_DEPLOYMENT` environment variable. For hybrid, set `OLLAMA_BASE_URL=http://localhost:11435`.

## Performance Considerations

### Session Caching
- Popular sessions are preloaded on startup
- Cache size is configurable (default: 50 sessions)
- Uses LRU eviction when cache is full

### Plot Generation
- Matplotlib backend set to 'Agg' for server environments
- Plots saved to BytesIO buffers for memory efficiency
- Figure cleanup after each plot generation

### AI Integration
- Optimized prompts with reduced context for faster inference
- Configurable timeout (300s default)
- Streaming support for real-time responses

## Common Development Patterns

### Adding New Telemetry Metrics
1. Modify `telemetry_metrics` list in `compare_fastest_laps()`
2. Add plotting function following `plot_telemetry()` pattern
3. Update `classify_moment()` for new metric classification

### Adding New Racing Moment Types
1. Extend `classify_moment()` function in `utils.py`
2. Add detection logic with appropriate thresholds
3. Include session-specific logic if needed (qualifying vs race)

### Extending AI Context
1. Modify `extract_telemetry_context()` in `utils.py`
2. Add new data fields to context dictionary
3. Update prompt formatting in `create_contextual_prompt()`

### Adding Input Validation
1. Add validation function to `validators.py`
2. Import and use in route handlers before processing
3. Return descriptive 400 errors for invalid inputs
4. Example pattern:
```python
from validators import validate_year, validate_driver

@app.route('/compare')
def compare():
    year = validate_year(request.args.get('year'))
    driver = validate_driver(request.args.get('driver'))
    # Use validated inputs...
```

## Development vs Production Workflow

### Development Environment (Port 5050)
```bash
# Start development server
./dev-start.sh

# Access development app
open http://localhost:5050
```

**Features:**
- Debug mode enabled
- Preloading disabled (faster startup)
- Single worker thread
- Safe for testing changes

### Production Environment (Port 5151)
```bash
# Restart production server (deploys changes to live site)
./prod-restart.sh

# Check production logs
tail -f prod.log
```

**Features:**
- Connected to Cloudflare tunnel (f1.linux-box.cc)
- Preloading enabled (better performance)
- Background process with logging
- Production-optimized settings

### Typical Development Workflow
1. **Make changes** to code files
2. **Test locally** on http://localhost:5050 using `./dev-start.sh`
3. **When satisfied**, deploy to production using `./prod-restart.sh`
4. **Verify live site** at https://f1.linux-box.cc

**Important:** The development and production environments run independently. Changes to development won't affect the live site until you explicitly restart production.

### Modal Deployment (Serverless GPU)

For serverless deployment with GPU-accelerated AI inference:

```bash
# Deploy to Modal
./deploy-modal.sh

# Your app runs at:
# https://your-username--f1-telemetry-flask-app.modal.run
```

**Features:**
- Serverless GPU (T4) for Ollama inference
- Auto-scaling to zero when idle
- $0/month (within $30 free tier for 10-20 queries/month)
- Sub-20 second response times (including cold starts)
- Persistent volume for FastF1 cache and models

**Cost Breakdown (15 queries/month):**
- GPU inference: $0.04
- Flask hosting: $0.01
- Storage (8GB): $0.80
- **Total: $0.85/month → $0 with free tier**

**Updating Modal deployment:**
```bash
# Make code changes, then:
modal deploy app_modal.py  # Zero-downtime deployment

# Or development mode with auto-reload:
modal serve app_modal.py
```

See [DEPLOY_MODAL.md](DEPLOY_MODAL.md) and [MIGRATION_SUMMARY.md](MIGRATION_SUMMARY.md) for complete details.

## FastF1 Cache Management

The application uses extensive caching for F1 data:
- **Cache Directory**: `fastf1_cache/` (hierarchical by year/race/session)
- **Cache Format**: FastF1 pickle files (`.ff1pkl`)
- **Cache Size**: Can grow to several GB with extensive usage
- **Cleanup**: Use `/clear_cache` endpoint or delete cache directory

## Critical Troubleshooting Guide

### Common Issues After Code Changes

#### 1. Plot Generation Issues (Black Screen)
**Symptoms**: Plot container shows black screen or empty plot
**Cause**: Plot buffer creation inside loops or incorrect matplotlib setup
**Fix**: Ensure `plot_buffer = BytesIO()` and `plt.savefig()` are positioned correctly after all plotting is complete

#### 2. Missing Moment Annotations
**Symptoms**: Clickable moments list disappears from result page
**Cause**: Context management broken, missing plot_annotations in template data
**Fix**: Verify `plot_annotations` is properly returned from `compare_fastest_laps()` and passed to template

#### 3. AI Analysis Failures (500 errors)
**Symptoms**: "Failed to analyze moment" or 500 errors on moment clicks
**Cause**: Incomplete telemetry context structure missing required fields
**Fix**: Ensure telemetry context includes complete structure:
```python
telemetry_context = {
    "plot_annotations": plot_annotations,
    "race_info": {"year": year, "race_name": race, "session_type": session_name},
    "driver1": {"name": drv1, "lap_time": float(time1)},
    "driver2": {"name": drv2, "lap_time": float(time2)},
    "comparison": {"faster_driver": faster, "delta": delta}
}
```

#### 4. Variable Scoping Errors (UnboundLocalError)
**Symptoms**: Result page broken with variable reference errors
**Cause**: Variables used before definition in context creation
**Fix**: Define variables like `session_name` before using them in context structures

### Infrastructure Notes

#### Cloudflare Tunnel Integration
- Production runs on port 5151 (connected to f1.linux-box.cc via LaunchAgent)
- Development runs on port 5050 (local testing only)
- LaunchAgent plist: `/Users/will/Library/LaunchAgents/com.f1app.cloudflared-tunnel.plist`
- Tunnel config: `/Users/will/.cloudflared/config.yaml`

## Deployment Notes

### Docker Configuration
- Uses multi-stage builds for smaller images
- Supports both standard and minimal requirements
- Includes health check endpoints

### SSL Setup
- Nginx reverse proxy configuration included
- Let's Encrypt certificate automation
- Cloudflare integration support

### Monitoring
- Prometheus metrics for request counts, latencies, and cache stats
- Structured logging for debugging and performance analysis
- Health check endpoints for load balancer integration

## Deployment Comparison

| Deployment | Cost/Month | AI Speed | Setup Time | Infrastructure | Notes |
|------------|------------|----------|------------|----------------|-------|
| **Local (Dev)** | $0 | 30-60s | Instant | Laptop running | Default |
| **Local (Prod)** | $0 | 30-60s | 2 min | Laptop + tunnel | Current |
| **Hybrid GPU** | **$0** | **5-10s** | **5 min** | **Laptop + Modal** | **⭐ Recommended** |
| **Docker** | $0-50 | 30-60s | 5 min | VPS/cloud | Self-hosted |
| **Modal (Full)** | $0 | 5-20s | 15 min | Fully managed | Reference |

**Recommendation:** Use **Hybrid GPU** for best performance ($0 cost, 5x faster AI, local data). The proxy is lightweight and Modal handles all GPU scaling.

## Security Considerations

### Input Validation
- All user inputs validated via `validators.py` module
- Prevents injection attacks, XSS, and path traversal
- Returns descriptive 400 errors for invalid inputs

### Secret Management
- Flask secret key stored in `.env.secret` (git-ignored)
- Never commit secrets to repository
- Use environment variables for sensitive config

### CORS and Security Headers
- CORS configured via `flask-cors`
- Security headers via `flask-talisman`
- Content compression via `flask-compress`

## Recent Architecture Changes

1. **Hybrid GPU Architecture (January 2025)** - Best of both worlds deployment
   - Local Flask/FastF1 for data operations (no timeouts)
   - Modal T4 GPU for AI inference only (5x speedup)
   - Lightweight proxy (`ollama_modal_proxy.py`) bridges local and cloud
   - $0/month cost, 5-10s AI responses (vs 30-60s on CPU)

2. **Enhanced AI Response Formatting** - Professional F1 broadcast styling
   - Red H1 titles (#ff3333) with uppercase and border
   - Bright blue H3 section headers (#3b9fff) with left accent
   - Auto-highlight driver names in golden yellow (#ffdd57) with glow
   - Auto-highlight metrics (times, speeds, RPM) in green (#4ade80) with monospace
   - Improved visual hierarchy and readability
   - Smart markdown parsing with paragraph breaks

3. **Simplified Modal Deployment** - `app_modal_ollama_only.py`
   - Ollama GPU function only (no Flask, no FastF1)
   - Builds custom f1-analyst model from llama3:8b base
   - Eliminates FastF1 download timeout issues
   - 15-minute timeout includes model building time

4. **Modal Proxy System** - `ollama_modal_proxy.py`
   - Drop-in replacement for local Ollama (port 11435)
   - Forwards to Modal via Python SDK (no local Ollama needed)
   - Health check and model listing endpoints
   - Lazy-loaded Modal connection for fast startup

5. **Production GPU Script** - `start-production-gpu.sh`
   - Environment-aware startup with GPU proxy
   - Proper OLLAMA_BASE_URL configuration
   - Clean process management

6. **Added Modal deployment support** - Serverless GPU platform integration
7. **Implemented input validation** - Security hardening via `validators.py`
8. **Created Ollama client abstraction** - Unified interface for local/Modal deployments
9. **Added deployment automation** - Shell scripts for dev/prod/Modal workflows
10. **Enhanced configuration management** - `ModalConfig` for serverless deployments

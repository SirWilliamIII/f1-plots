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

### Key Features

- **5-panel telemetry plots**: Throttle, Brake, RPM, Speed, and Gear comparison
- **AI-powered analysis**: Contextual telemetry insights via Ollama integration
- **Performance caching**: Background preloading of popular F1 sessions
- **Moment classification**: Automatic identification of racing techniques (trail braking, gear selection, etc.)
- **Prometheus metrics**: Built-in performance monitoring

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
- Two specialized models: `f1expert.modelfile` and `f1-analyst.modelfile`
- Includes comprehensive telemetry data in prompts with driver mappings
- Supports both streaming and non-streaming responses
- Temperature optimized for speed (0.2-0.3) with focused context window

### Moment Classification (`utils.py:1-168`)
- Analyzes telemetry data to identify racing techniques
- Differentiates between qualifying and race scenarios
- Detects: trail braking, gear selection, throttle application, overtakes, etc.
- Provides contextual descriptions for plot annotations

## Environment Configuration

### Required Environment Variables
```bash
OLLAMA_BASE_URL=http://ollama:11434  # Ollama service URL
FLASK_ENV=development|production     # Environment mode
PORT=8080                           # Application port
```

### Configuration Files
- **`config.py`**: Tunable parameters for session management, Flask, and Gunicorn
- **`requirements.txt`**: Python dependencies (use with `uv pip install`)
- **`requirements-minimal.txt`**: Minimal dependencies for Docker builds
- **`pyproject.toml`**: Project metadata and uv configuration
- **`uv.lock`**: Locked dependency versions for reproducible builds

## Data Flow

1. **User Request**: Select year/race/session/drivers via web interface
2. **Session Loading**: SessionManager checks cache or loads from FastF1
3. **Telemetry Processing**: Extract and process driver telemetry data
4. **Plot Generation**: Create 5-panel comparison with moment annotations
5. **AI Analysis**: Generate contextual insights using Ollama
6. **Response**: Serve plot and analysis to user

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

## Summary of Key Changes

1. **Added AI Architecture Philosophy** section explaining the "pattern explainer" approach
2. **Documented Modelfile Design Decisions** with specific parameters and rationale
3. **Included Optimal Prompt Engineering** patterns with concrete examples
4. **Added Performance vs Accuracy Trade-offs** section with practical thresholds
5. **Enhanced Development Best Practices** with testing examples and quality metrics
6. **Outlined Future Enhancements** for pattern recognition and multi-model approaches

This update captures the key insights from our discussion while maintaining the practical, development-focused nature of your Claude.md file.

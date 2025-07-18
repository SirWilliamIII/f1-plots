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

### Local Development
```bash
# Install dependencies
uv pip install -r requirements.txt

# Run development server
python app.py

# Run with production server
gunicorn app:app -c gunicorn.conf.py
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
# Check cache statistics
curl http://localhost:8080/cache_stats

# Clear session cache
curl -X POST http://localhost:8080/clear_cache

# Health check
curl http://localhost:8080/health

# Prometheus metrics
curl http://localhost:8080/metrics
```

## Key Implementation Details

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
- Optimized for speed with reduced context window and temperature
- Includes comprehensive telemetry data in prompts
- Supports both streaming and non-streaming responses

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
- **`requirements.txt`**: Python dependencies
- **`pyproject.toml`**: Project metadata and dependencies

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

## FastF1 Cache Management

The application uses extensive caching for F1 data:
- **Cache Directory**: `fastf1_cache/` (hierarchical by year/race/session)
- **Cache Format**: FastF1 pickle files (`.ff1pkl`)
- **Cache Size**: Can grow to several GB with extensive usage
- **Cleanup**: Use `/clear_cache` endpoint or delete cache directory

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
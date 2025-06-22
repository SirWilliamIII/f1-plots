# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Application

**Oracle Cloud Production Deployment:**
```bash
# Automated deployment (recommended)
chmod +x deploy-oracle.sh
./deploy-oracle.sh

# Manual Docker deployment
docker build -t f1-race-plots .
docker run -d --name f1-plots-container \
  -p 8080:8080 \
  -v /opt/f1-plots-data/fastf1_cache:/app/fastf1_cache \
  f1-race-plots

# Development mode
python app.py
```

**Local Development:**
```bash
# With Gunicorn
gunicorn --bind 0.0.0.0:8080 --timeout 900 --workers 1 app:app

# Direct Flask (development only)
python app.py
```

### Dependencies
```bash
# Install requirements
pip install -r requirements.txt

# Key dependencies: Flask, FastF1, matplotlib, pandas, numpy
```

### Testing
```bash
# No formal test suite - manual testing via web interface
# Test endpoints: /, /get_races, /get_drivers, /health, /metrics
```

## Architecture Overview

### Core Components

**Flask Web Application (app.py)**
- Main telemetry comparison web service
- Routes: index, get_races, get_drivers, ollama_proxy
- Generates F1 telemetry plots comparing two drivers
- Integrates with Ollama for AI analysis of telemetry data

**Session Manager (session_manager.py)**
- Handles FastF1 session caching and preloading
- Thread-safe session management with background preloading
- Optimizes performance by caching popular race sessions
- Prevents API timeouts with smart error handling

**Telemetry Analysis (utils.py)**
- classify_moment(): Advanced telemetry moment classification
- Identifies racing techniques: braking points, throttle application, gear selection
- Context-aware analysis for qualifying vs race sessions

**Configuration (config.py)**  
- Centralized settings for SessionManager, Flask, and Gunicorn
- Environment-specific configurations (dev/prod)

### Data Flow
1. User selects year/race/session/drivers via web form
2. Session Manager retrieves FastF1 session data (cached or fresh)
3. compare_fastest_laps() generates telemetry comparison plots
4. extract_telemetry_context() creates data for AI analysis
5. Plot served to user with optional Ollama AI commentary

### Key Features
- **Telemetry Visualization**: 4-panel plots (Throttle, Brake, RPM, Speed)
- **Intelligent Annotations**: Moment classification with racing insights
- **Session Caching**: Background preloading of popular sessions
- **AI Integration**: Ollama proxy for telemetry analysis
- **Performance Monitoring**: Prometheus metrics integration

### FastF1 Integration
- Uses fastf1_cache/ directory for F1 API data caching
- Preloads popular sessions (Monaco, Silverstone, etc.)
- Handles session types: "Q" (Qualifying), "R" (Race)
- Telemetry channels: Throttle, Brake, Speed, RPM, Distance, Time

### Frontend Structure
- templates/: Jinja2 HTML templates (index, result, error)
- static/: CSS, JavaScript, and generated plot images
- JavaScript handles dynamic form updates and error handling

## Development Notes

### Performance Considerations
- Session Manager uses ThreadPoolExecutor for background loading
- matplotlib configured with Agg backend for server environments
- FastF1 cache reduces API calls and improves response times
- Compression enabled for HTTP responses

### Error Handling
- Graceful fallbacks for missing telemetry data
- Timeout protection for slow FastF1 API calls
- User-friendly error messages for common failures

### Ollama Integration
- Local Ollama server expected at localhost:11434
- AI analysis focuses only on visible plot data
- Enhanced prompts with specific telemetry context injection

### Memory Management
- Cache cleanup preserves popular sessions
- Matplotlib figures properly closed to prevent leaks
- Thread pool gracefully shut down on app exit

## Deployment

### Oracle Cloud Setup
- Deployed via Docker container on Oracle Cloud VM
- Uses deploy-oracle.sh for automated deployment
- Requires Security Group configuration for port 8080
- See ORACLE_CLOUD_SETUP.md for detailed network configuration

### Environment Variables
- `PORT`: Application port (default: 8080)
- `OLLAMA_BASE_URL`: Ollama service URL (default: http://localhost:11434)
- `PYTHONUNBUFFERED`: Logging configuration
- `MATPLOTLIB_BACKEND`: Set to Agg for headless operation

### Docker Configuration
- Multi-stage build for smaller image size
- Persistent FastF1 cache via volume mounts
- Health check endpoint at /health
- Prometheus metrics at /metrics
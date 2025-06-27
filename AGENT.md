# Agent Instructions for F1 Race Plots

## Commands
- **Run app**: `python app.py` (development) or `gunicorn app:app` (production)
- **Install deps**: `pip install -r requirements.txt`
- **Docker build**: `docker build -t f1-race-plots .`
- **Docker run**: `docker run -p 8080:8080 f1-race-plots`
- **Tests**: `pytest` (framework configured in .qodo/testConfig.toml)

## Architecture
- **Flask app** (`app.py`): Main web server with telemetry visualization endpoints
- **Session Manager** (`session_manager.py`): Thread-safe F1 session caching with background preloading
- **Utils** (`utils.py`): Racing moment classification and telemetry context extraction
- **Config** (`config.py`): Centralized configuration management
- **FastF1 integration**: Fetches F1 telemetry data with caching in `fastf1_cache/`
- **AI integration**: Ollama proxy for telemetry analysis with contextual prompts

## Key APIs
- `/` - Main interface for driver telemetry comparison
- `/get_races` - Race list for selected year
- `/get_drivers` - Driver list for race/session
- `/ollama_proxy/generate` - AI analysis with telemetry context
- `/cache_stats` - Debug session cache status

## Code Style
- **Imports**: Flask utilities first, then FastF1, then data processing (matplotlib, pandas, numpy)
- **Error handling**: Try/catch with proper logging and user-friendly error messages
- **Functions**: Well-documented with type hints where appropriate
- **Global state**: Managed through SessionManager and current_telemetry_context
- **Logging**: Use logging module with INFO level for operations, ERROR for failures
- **Threading**: Thread-safe operations with locks for cache management

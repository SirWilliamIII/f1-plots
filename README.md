# F1 Race Plots

A web application for visualizing and comparing Formula 1 telemetry data with AI-powered analysis. Generate detailed telemetry plots comparing two drivers' performance from any F1 session.

![Demo](https://f1-plots.app)

## Features

- **Telemetry Visualization**: Generate 4-panel comparison plots (Throttle, Brake, RPM, Speed)
- **AI Analysis**: Integrated Ollama AI for intelligent telemetry insights
- **Session Caching**: Background preloading of popular F1 sessions for fast performance
- **Comprehensive Data**: Access to historical F1 data from 2020-2025
- **Moment Classification**: Advanced racing technique identification
- **Performance Monitoring**: Built-in Prometheus metrics

## Quick Start

### Option 1: Python

```bash
git clone https://github.com/yourusername/f1-race-plots.git
cd f1-race-plots
pip install -r requirements.txt
python app.py
```

Visit [http://127.0.0.1:5000](http://127.0.0.1:5000)

### Option 2: Docker

```bash
docker build -t f1-race-plots .
docker run -p 8080:8080 f1-race-plots
```

Visit [http://localhost:8080](http://localhost:8080)

### Option 3: Docker Compose

```bash
docker-compose up
```

## Architecture

- **Flask Web App** (`app.py`): Main telemetry comparison service
- **Session Manager** (`session_manager.py`): Thread-safe F1 session caching
- **Telemetry Analysis** (`utils.py`): Racing technique classification
- **Configuration** (`config.py`): Centralized settings management

## API Endpoints

- `/` - Main web interface
- `/get_races` - Available races for selected year
- `/get_drivers` - Drivers for selected race/session
- `/health` - Health check
- `/metrics` - Prometheus metrics
- `/ollama_proxy` - AI analysis proxy

## Dependencies

Key technologies:
- **FastF1**: F1 telemetry data API
- **Flask**: Web framework
- **Matplotlib**: Plot generation
- **Pandas/NumPy**: Data processing
- **Ollama**: AI analysis integration

## Configuration

Environment variables:
- `PORT`: Application port (default: 8080)
- `OLLAMA_BASE_URL`: Ollama service URL
- `FLASK_ENV`: Environment (development/production)

## Development

See `DESCRIPTION.md` for detailed development guidance and architecture overview.

## Credits

- [FastF1](https://theoehrly.github.io/Fast-F1/) - F1 telemetry data
- [Flask](https://flask.palletsprojects.com/) - Web framework
- [Ollama](https://ollama.ai/) - AI integration

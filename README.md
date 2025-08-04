# F1 Race Plots

A web application for visualizing and comparing Formula 1 telemetry data with AI-powered analysis. Generate detailed telemetry plots comparing two drivers' performance from any F1 session.

![Demo](https://f1-plots.app)

## Features

- **Telemetry Visualization**: Generate 5-panel comparison plots (Throttle, Brake, RPM, Speed, Gear)
- **AI Analysis**: Integrated Ollama AI for intelligent telemetry insights
- **Session Caching**: Background preloading of popular F1 sessions for fast performance
- **Comprehensive Data**: Access to historical F1 data from 2020-2025
- **Moment Classification**: Advanced racing technique identification
- **Performance Monitoring**: Built-in Prometheus metrics

## Quick Start

### Option 1: Python with uv

```bash
git clone https://github.com/yourusername/f1-race-plots.git
cd f1-race-plots
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh
# Install dependencies with uv
uv pip install -r requirements.txt
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

### Option 4: Podman

#### Method A: Using deploy-podman.sh (Recommended)

```bash
# Install Podman if not already installed
# For Ubuntu/Debian: sudo apt install podman
# For macOS: brew install podman
# For other systems: https://podman.io/getting-started/installation

# Run the deployment script
./deploy-podman.sh
```

Visit [http://localhost:8080](http://localhost:8080)

#### Method B: Using podman-compose

```bash
# Install Podman if not already installed
# For Ubuntu/Debian: sudo apt install podman
# For macOS: brew install podman

# Use the wrapper script (installs podman-compose if needed)
./podman-compose-wrapper.sh up -d
```

Visit [http://localhost:8080](http://localhost:8080)

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

## SSL Setup with Nginx and Cloudflare

### Prerequisites
- A domain name registered with Cloudflare
- A server with Docker and docker-compose installed
- Port 80 and 443 open on your server

### Step 1: Configure Cloudflare DNS
1. Log in to your Cloudflare account
2. Select your domain
3. Go to the DNS tab
4. Add A records pointing to your server's IP address:
   - Type: A, Name: @ (or your subdomain), Content: YOUR_SERVER_IP
   - Type: A, Name: www, Content: YOUR_SERVER_IP
5. Set the proxy status to "DNS only" (gray cloud) initially

### Step 2: Set Up SSL with Let's Encrypt
1. Clone this repository to your server
2. Make the initialization script executable:
   ```bash
   chmod +x init-letsencrypt.sh
   ```
3. Run the script and follow the prompts:
   ```bash
   ./init-letsencrypt.sh
   ```
4. The script will:
   - Ask for your domain name and email
   - Create temporary certificates
   - Obtain real certificates from Let's Encrypt
   - Configure Nginx with your domain

### Step 3: Start the Application with SSL
```bash
docker-compose -f docker-compose.ssl.yml up -d
```

### Step 4: Update Cloudflare Settings (Optional)
1. Go back to Cloudflare DNS settings
2. Change the proxy status to "Proxied" (orange cloud)
3. Go to SSL/TLS settings and set the encryption mode to "Full" or "Full (strict)"

This setup provides:
- HTTPS encryption with auto-renewing certificates
- Optional Cloudflare proxy for additional security and performance

## Development

See `DESCRIPTION.md` for detailed development guidance and architecture overview.

## Credits

- [FastF1](https://theoehrly.github.io/Fast-F1/) - F1 telemetry data
- [Flask](https://flask.palletsprojects.com/) - Web framework
- [Ollama](https://ollama.ai/) - AI integration

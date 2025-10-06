# F1 Race Plots

## Project Overview

This is a Python Flask web application for visualizing and comparing Formula 1 telemetry data. It allows users to select a year, race, and two drivers, and then generates a detailed telemetry plot comparing their performance. The application also includes an AI-powered analysis feature using Ollama.

**Main Technologies:**

*   **Backend:** Python, Flask, Gunicorn
*   **Data:** FastF1 library
*   **Plotting:** Matplotlib
*   **Frontend:** HTML, CSS, JavaScript
*   **AI Analysis:** Ollama
*   **Containerization:** Docker, Docker Compose
*   **Web Server:** Nginx (for SSL)

**Architecture:**

*   `app.py`: The main Flask application that handles routing, data processing, and plot generation.
*   `session_manager.py`: Manages loading and caching of FastF1 session data.
*   `utils.py`: Contains helper functions, including `classify_moment` for analyzing telemetry data.
*   `config.py`: Centralized configuration for the application.
*   `templates/`: Contains the HTML templates for the web interface.
*   `static/`: Contains the CSS and JavaScript files for the frontend.
*   `Dockerfile`: Defines the Docker image for the application.
*   `docker-compose.yml`: Defines the services for running the application with Docker Compose (Flask app and Ollama).
*   `nginx/nginx.conf`: Nginx configuration for proxying requests to the Flask app and handling SSL.

## Building and Running

### Local Development (Python with uv)

1.  Install dependencies:
    ```bash
    uv pip install -r requirements.txt
    ```
2.  Run the application:
    ```bash
    python app.py
    ```

### Docker

1.  Build the Docker image:
    ```bash
    docker build -t f1-race-plots .
    ```
2.  Run the Docker container:
    ```bash
    docker run -p 8080:8080 f1-race-plots
    ```

### Docker Compose

1.  Start the application:
    ```bash
    docker-compose up
    ```

## Development Conventions

*   The project uses a `.python-version` file, suggesting a specific Python version is intended.
*   It uses `uv` for package management.
*   The code is structured into modules with clear responsibilities.
*   The application is designed to be containerized with Docker.
*   There is a clear separation of concerns between the backend (Python/Flask) and the frontend (HTML/CSS/JS).
*   The `dev-start.sh` script can be used to simplify the development startup process.
*   The `README.md` is comprehensive and provides good documentation.

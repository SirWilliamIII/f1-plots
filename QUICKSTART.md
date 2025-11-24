# Quick Start Guide

## Running the App Locally

### Option 1: Using the Dev Script (Recommended)

```bash
./scripts/dev-start.sh
```

This will:

- Start development server on port **5050**
- Enable debug mode
- Set `FLASK_ENV=development`
- Access at: http://localhost:5050

### Option 2: Direct Python Execution

```bash
# With uv (recommended)
uv run python run.py

# Or with standard Python
python run.py
```

Default port: **5151** (production settings)

### Option 3: Custom Port/Settings

```bash
# Set custom port
export PORT=8080
export FLASK_ENV=development
python run.py
```

## Prerequisites

### 1. Install Dependencies

```bash
# Install uv (fast Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
uv pip install -r requirements.txt
```

### 2. Set up Ollama Models (Optional - for AI features)

```bash
# Create F1-specific models
ollama create f1-analyst -f f1-analyst.modelfile
ollama create f1expert -f f1expert.modelfile

# Verify models
ollama list | grep f1
```

## Access the Application

Once running, open your browser to:

- **Development**: <http://localhost:5050>
- **Production**: <http://localhost:5151>

## First Time Setup

1. **Clone the repository**

   ```bash
   git clone <your-repo-url>
   cd f1-race-plots
   ```

2. **Install dependencies**

   ```bash
   uv pip install -r requirements.txt
   ```

3. **Run the app**

   ```bash
   ./scripts/dev-start.sh
   ```

4. **Select a race and compare drivers!**

## Troubleshooting

### Port Already in Use

```bash
# Find process using the port
lsof -i :5050

# Kill the process
kill -9 <PID>
```

### Missing Dependencies

```bash
# Reinstall all dependencies
uv pip install -r requirements.txt --force-reinstall
```

### Import Errors

Make sure you're running from the project root directory:

```bash
cd /path/to/f1-race-plots
python run.py
```

## Development Workflow

1. **Make changes** to code in `app/` directory
2. **Save files** (Flask auto-reloads in debug mode)
3. **Refresh browser** to see changes
4. **Check logs** in terminal for errors

## Environment Variables

| Variable          | Default             | Description        |
| ----------------- | ------------------- | ------------------ |
| `PORT`            | 5151                | Server port        |
| `FLASK_ENV`       | production          | Environment mode   |
| `OLLAMA_BASE_URL` | http://ollama:11434 | Ollama service URL |

## Next Steps

- See `/docs/CLAUDE.md` for complete documentation
- See `/scripts/README.md` for deployment options
- See `/docs/DEPLOY_HYBRID.md` for GPU acceleration setup

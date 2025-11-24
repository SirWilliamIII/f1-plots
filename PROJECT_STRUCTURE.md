# F1 Telemetry Application - Project Structure

## Overview

This document describes the reorganized project structure after comprehensive refactoring.

## Directory Structure

```
f1-race-plots/
├── app/                          # Modular Flask application
│   ├── __init__.py              # App factory (79 lines)
│   ├── metrics.py               # Shared Prometheus metrics (15 lines)
│   ├── services/                # Business logic
│   │   ├── memory_service.py    # Memory monitoring (86 lines)
│   │   ├── context_service.py   # Session context (55 lines)
│   │   └── ai_service.py        # AI prompt creation (61 lines)
│   ├── plotting/                # Telemetry visualization
│   │   └── telemetry_plots.py   # Plot generation (701 lines)
│   ├── middleware/              # Request/response handling
│   │   └── cleanup.py           # Memory cleanup hooks (71 lines)
│   └── routes/                  # API endpoints
│       ├── ollama_routes.py     # Ollama proxy (109 lines)
│       ├── api_routes.py        # Data APIs (229 lines)
│       ├── cache_routes.py      # Cache management (73 lines)
│       ├── main_routes.py       # Main app routes (169 lines)
│       ├── plot_routes.py       # Plot serving (19 lines)
│       └── memory_routes.py     # Memory monitoring (83 lines)
│
├── scripts/                     # Deployment & utility scripts
│   ├── README.md               # Scripts documentation
│   ├── dev-start.sh            # Development server
│   ├── start-production-gpu.sh # Production with GPU
│   ├── deploy-to-oracle.sh     # Oracle Cloud deployment
│   ├── deploy-oracle-hybrid.sh # Hybrid GPU deployment
│   ├── update-oracle.sh        # Update Oracle deployment
│   ├── oracle-manage.sh        # Oracle management
│   └── deploy-modal.sh         # Modal serverless deployment
│
├── docs/                        # Documentation
│   ├── README.md               # Documentation index
│   ├── CLAUDE.md               # Main project reference
│   ├── DEPLOY_ORACLE.md        # Oracle deployment guide
│   └── ORACLE_QUICKSTART.md    # Quick start guide
│
├── tests/                       # Test files
│   └── test_modal_proxy.py     # Modal proxy tests
│
├── templates/                   # Jinja2 HTML templates
│   ├── index.html
│   ├── result.html
│   └── error.html
│
├── static/                      # Static assets
│   ├── css/
│   ├── js/
│   └── styles.css
│
├── fastf1_cache/                # FastF1 telemetry cache (gitignored)
│
├── run.py                       # Application entry point
├── config.py                    # Configuration
├── session_manager.py           # Session caching
├── utils.py                     # Utility functions
├── ollama_client.py             # Ollama client
├── ollama_modal_proxy.py        # Modal GPU proxy
├── app_modal.py                 # Modal deployment (full)
├── app_modal_ollama_only.py     # Modal deployment (GPU only)
│
├── requirements.txt             # Python dependencies
├── requirements-minimal.txt     # Minimal dependencies
├── pyproject.toml               # Project metadata
├── uv.lock                      # Locked dependencies
├── README.md                    # Project README
└── .gitignore                   # Git ignore rules

```

## Key Improvements from Refactoring

### 1. Code Organization

**Before:** 1,551-line monolithic `app.py`
**After:** 16 modular files with clear separation of concerns

### 2. Maintainability

- Each module has a single, well-defined responsibility
- Easy to locate and modify specific functionality
- Independent testing of modules

### 3. File Organization

- **Scripts**: All deployment/utility scripts in `/scripts`
- **Documentation**: Comprehensive guides in `/docs`
- **Tests**: Test files in `/tests`
- **Clean root**: Only essential project files

### 4. Scalability

- New routes can be added without touching existing code
- Services can be extended independently
- Middleware can be layered easily

## Running the Application

### Development

```bash
./scripts/dev-start.sh
# OR
python run.py
```

### Production (Local with GPU)

```bash
./scripts/start-production-gpu.sh
```

### Production (Oracle Cloud)

```bash
./scripts/deploy-to-oracle.sh
```

### Production (Modal Serverless)

```bash
./scripts/deploy-modal.sh
```

## Module Descriptions

### app/

- **metrics.py**: Shared Prometheus metrics (prevents duplicate registration)

### app/services/

- **memory_service.py**: Memory monitoring, garbage collection, leak prevention
- **context_service.py**: Session context storage and retrieval for AI analysis
- **ai_service.py**: AI prompt creation and formatting

### app/plotting/

- **telemetry_plots.py**: Complete telemetry plot generation with annotations

### app/middleware/

- **cleanup.py**: Request cleanup hooks, session manager initialization

### app/routes/

- **ollama_routes.py**: Proxy endpoints for Ollama AI integration
- **api_routes.py**: Race/driver data endpoints, moment analysis
- **cache_routes.py**: Cache statistics and management
- **main_routes.py**: Main index and comparison routes
- **plot_routes.py**: Plot image serving
- **memory_routes.py**: Memory monitoring endpoints

## Total Line Count Comparison

**Before Refactoring:**

- app.py: 1,551 lines

**After Refactoring:**

- Total modular code: ~1,793 lines across 17 files
- Largest file: telemetry_plots.py (701 lines)
- Average file size: ~105 lines

**Result:** No file exceeds 1,000 lines, much easier to navigate and maintain.

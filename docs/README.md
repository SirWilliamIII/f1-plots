# F1 Telemetry Application Documentation

This directory contains comprehensive documentation for deployment, architecture, and development.

## Documentation Files

### Main Documentation
- **`CLAUDE.md`** - Complete project reference for Claude Code AI assistant
  - Architecture overview
  - Development workflows
  - Deployment configurations
  - Troubleshooting guides

### Deployment Guides

#### Hybrid GPU Architecture (Recommended)
- **`DEPLOY_HYBRID.md`** - Hybrid deployment guide
  - Local Flask/FastF1 + Modal T4 GPU
  - $0/month cost, 5x faster AI (5-10s vs 30-60s)
  - Best of both worlds approach

#### Cloud Deployments
- **`DEPLOY_ORACLE.md`** - Oracle Cloud Infrastructure deployment
  - Ubuntu 22.04 ARM64
  - Production setup with nginx
  - Cloudflare integration

- **`ORACLE_QUICKSTART.md`** - Quick start guide for Oracle Cloud

- **`DEPLOY_MODAL.md`** - Modal serverless platform deployment
  - Full serverless deployment
  - GPU-accelerated AI inference
  - Auto-scaling architecture

### Migration & Architecture
- **`MIGRATION_SUMMARY.md`** - Architecture changes and migration history
  - GPU integration timeline
  - Performance improvements
  - Deployment evolution

## Quick Links

### Getting Started
1. Read `CLAUDE.md` for complete project overview
2. Choose deployment method from guides above
3. Run appropriate script from `/scripts` folder

### Common Tasks
- **Local Development**: See `CLAUDE.md` → "Development Commands"
- **Hybrid GPU Setup**: See `DEPLOY_HYBRID.md`
- **Oracle Deployment**: See `DEPLOY_ORACLE.md` + `ORACLE_QUICKSTART.md`
- **Modal Deployment**: See `DEPLOY_MODAL.md`

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│  Deployment Options                                  │
├─────────────────────────────────────────────────────┤
│                                                      │
│  1. Local Development (dev-start.sh)                 │
│     └─ Flask on port 5050, local CPU                │
│                                                      │
│  2. Hybrid GPU (Recommended)                         │
│     ├─ Local: Flask (5151) + FastF1                 │
│     └─ Cloud: Modal T4 GPU for AI only              │
│                                                      │
│  3. Oracle Cloud Production                          │
│     ├─ Flask + nginx + Cloudflare                   │
│     └─ Hybrid GPU via Modal proxy                   │
│                                                      │
│  4. Full Modal Serverless                            │
│     └─ Everything on Modal (Flask + GPU)            │
│                                                      │
└─────────────────────────────────────────────────────┘
```

## Support & Troubleshooting

See `CLAUDE.md` → "Critical Troubleshooting Guide" for common issues and solutions.

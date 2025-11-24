# Deployment & Utility Scripts

This directory contains all shell scripts for deployment, development, and management.

## Development Scripts

- **`dev-start.sh`** - Start development server (port 5050)
  ```bash
  ./scripts/dev-start.sh
  ```

## Production & Deployment

### Local Production
- **`start-production-gpu.sh`** - Start production server with GPU proxy (port 5151)

### Oracle Cloud Deployment
- **`deploy-to-oracle.sh`** - Deploy application to Oracle Cloud VM
- **`deploy-oracle-hybrid.sh`** - Deploy hybrid GPU architecture to Oracle
- **`update-oracle.sh`** - Update existing Oracle deployment
- **`oracle-manage.sh`** - Management utilities for Oracle deployment

### Modal Serverless Deployment
- **`deploy-modal.sh`** - Deploy to Modal serverless platform with T4 GPU

## Usage Notes

All scripts should be run from the project root directory:
```bash
./scripts/dev-start.sh
./scripts/deploy-to-oracle.sh
```

See the documentation in `/docs` for detailed deployment guides.

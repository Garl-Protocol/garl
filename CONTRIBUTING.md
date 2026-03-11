# Contributing to GARL Protocol

Thank you for your interest in contributing. This guide explains how to set up the development environment, run tests, and submit changes.

## Development Environment

The project uses FastAPI (backend) and Next.js 14 (frontend).

**Backend (Python 3.12):**
```bash
pip install -r backend/requirements.txt
```

**Frontend (Node 20):**
```bash
cd frontend/
npm install
```

## Running Tests

**Backend:**
```bash
python3 -m pytest backend/tests/
```

**Frontend:**
```bash
cd frontend/
npx next build
```

## Pull Request Process

1. Fork the repository and create a branch from `main`.
2. Make your changes and ensure all tests pass.
3. Submit a pull request with a clear description of the changes.
4. Address any review feedback. Maintainers will merge once approved.

## Code Style

- **Python:** Follow PEP 8. Use a formatter such as Black or Ruff.
- **TypeScript:** Follow ESLint and Prettier configuration in the project.

## Questions

Open an issue on the repository for questions or discussions.

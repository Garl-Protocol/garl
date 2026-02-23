# Contributing to GARL Protocol

Thank you for your interest in contributing to the Global Agent Reputation Ledger. This guide will help you get started.

## Getting Started

1. **Fork** the repository
2. **Clone** your fork locally
3. **Create a branch** from `main` for your work
4. **Make your changes** following the guidelines below
5. **Submit a Pull Request** back to this repo

## Development Setup

```bash
git clone https://github.com/<your-username>/garl.git
cd garl
cp backend/.env.example backend/.env
# Fill in your Supabase credentials
docker compose up --build
```

Backend runs on `http://localhost:8000`, frontend on `http://localhost:3000`.

## Code Guidelines

- **Backend**: Python 3.12+, FastAPI, type hints required, Pydantic models for all request/response schemas
- **Frontend**: Next.js 14 (App Router), TypeScript strict mode, Tailwind CSS for styling
- **Tests**: All new endpoints must include pytest tests. Run with `cd backend && pytest`
- **Formatting**: Follow existing code style. No lint warnings in PRs

## What to Contribute

- Bug fixes with reproduction steps
- New trust dimensions or scoring improvements
- SDK improvements (Python, JavaScript)
- MCP server tool additions
- A2A protocol enhancements
- Documentation improvements
- Performance optimizations

## Pull Request Process

1. Ensure your branch is up to date with `main`
2. Include a clear description of what changed and why
3. Reference any related issues
4. All CI checks must pass
5. Maintainers will review within 48 hours

## Reporting Issues

Use [GitHub Issues](https://github.com/Garl-Protocol/garl/issues) with the appropriate template. Include:

- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python/Node version)

## Code of Conduct

Be respectful, constructive, and professional. We are building trust infrastructure — let's model that in our community interactions.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

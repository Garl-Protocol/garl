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

## Developer Certificate of Origin (DCO)

Every commit must be **signed off** to certify that you wrote the code, or otherwise have the right to contribute it under the project's Apache 2.0 license. This is the standard [DCO 1.1](https://developercertificate.org/) used by the Linux kernel, Docker, and most Apache Software Foundation projects.

Sign off your commits with `git commit -s` (or `--signoff`). That appends a `Signed-off-by: Your Name <your.email@example.com>` trailer. Without the trailer, maintainers will ask you to amend the commit before merging. If you set it up once — `git config --global format.signOff true` — it happens automatically.

Please do **not** use `--no-verify` or edit the trailer by hand.

## Pull Request Process

1. Fork the repository and create a branch from `main`.
2. Make your changes and ensure all tests pass (`python3.12 -m pytest backend/tests/` + `npx next build` in `frontend/`).
3. Sign off your commits (see DCO above).
4. Submit a pull request with a clear description of the changes and which audit finding / issue / roadmap phase it addresses.
5. Address any review feedback. Maintainers will merge once approved and CI is green.

Review timelines: routine changes typically get a first response within 3 business days. Protocol-level changes (new endpoints, receipt shape, scoring tweaks) need a public comment period per [GOVERNANCE.md](GOVERNANCE.md).

## Code Style

- **Python:** Follow PEP 8. Use a formatter such as Black or Ruff.
- **TypeScript:** Follow ESLint and Prettier configuration in the project.

## Governance and Trademark

Project decision-making is documented in [GOVERNANCE.md](GOVERNANCE.md). Use of the GARL name and marks is covered in [TRADEMARK.md](TRADEMARK.md). Contributions to the repository are accepted under Apache 2.0 — please read these before opening a PR that touches naming, branding, or governance surfaces.

## Questions

Open an issue on the repository for questions or discussions.

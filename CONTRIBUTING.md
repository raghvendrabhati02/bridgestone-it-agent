# Contributing to Bridgestone IT AI Assistant

Thank you for your interest in contributing to the **Bridgestone IT AI Assistant**! We welcome contributions from developers, QA engineers, and technical writers.

Please take a moment to review this document to understand our development setup, contribution guidelines, and submission workflow.

---

## Code of Conduct

All contributors are expected to adhere to our [Code of Conduct](./CODE_OF_CONDUCT.md). Please report any unacceptable behavior to project maintainers.

---

## Development Environment Setup

### Prerequisites
- **Python:** Version 3.12+
- **Node.js:** Version 18+
- **Package Managers:** `pip` and `npm`

### 1. Clone the Repository
```bash
git clone https://github.com/raghvendrabhati02/bridgestone-it-agent.git
cd bridgestone-it-agent
```

### 2. Backend Setup
```bash
cd backend
python -m venv venv_312

# On Windows PowerShell:
.\venv_312\Scripts\activate

# On Linux/macOS:
source venv_312/bin/activate

pip install -r requirements.txt
```

### 3. Frontend Setup
```bash
cd frontend
npm install
```

---

## Development Workflow & Coding Standards

### 1. Branching Naming Strategy
Use descriptive branch names prefixed with the category of change:
- `feature/` for new functionality (e.g., `feature/laps-cyberark-adapter`)
- `fix/` for bug fixes (e.g., `fix/servicenow-choice-resolver`)
- `docs/` for documentation updates (e.g., `docs/api-reference-update`)

### 2. Python Standards (Backend)
- Follow **PEP 8** formatting guidelines.
- Use explicit type annotations for function signatures.
- Handle exceptions safely using context loggers (`logger.error(...)`) rather than bare `except Exception: pass`.
- Do not make blocking calls on async event loop threads.

### 3. TypeScript / React Standards (Frontend)
- Use strict TypeScript interfaces for all components and state models.
- Avoid using `any` types wherever possible.
- Maintain responsive layouts and custom CSS tokens defined in `frontend/src/app/globals.css`.

---

## Running Verification Tests

Before submitting a Pull Request, ensure that all unit and integration tests pass cleanly:

### Backend Test Suite
```bash
cd backend
.\venv_312\Scripts\python.exe -m pytest tests/ -v
```

### Frontend Build Verification
```bash
cd frontend
npm run build
```

---

## Submitting a Pull Request (PR)

1. **Fork & Branch:** Create a feature branch from `main`.
2. **Commit Messages:** Write clear, descriptive commit messages (e.g. `feat(servicenow): add OAuth2 token refresh fallback logic`).
3. **Keep PRs Focused:** Limit PRs to a single logical feature or fix.
4. **Update Documentation:** If your changes add or modify API endpoints, update [docs/API.md](./docs/API.md).
5. **Fill out PR Template:** Follow the structured checklist in the Pull Request template.

Thank you for helping build an enterprise-grade AI IT Assistant!

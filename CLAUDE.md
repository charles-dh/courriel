# CLAUDE.md

Agent-specific guidelines for working with the ResaBot FastAPI codebase.

This CLAUDE.md should remain focused on **workflow** while @README.md is the source of truth for **implementation**.

## Essential Commands

### Dependency Management

```bash
uv add <package>        # Add a new dependency
uv remove <package>     # Remove a dependency
uv sync                 # Sync dependencies with uv.lock
uv run <command>        # Run command in project environment
```

**Always use `uv` for dependency management.** Do not use `pip` directly.

### Code Quality

```bash
uv run ruff check .              # Check for linting issues
uv run ruff check --fix .        # Auto-fix linting issues
uv run ruff format .             # Format code
```

**Run `ruff` after making code changes** to ensure consistency.

### Testing

```bash
uv run pytest                    # Run all tests
uv run pytest tests/test_foo.py  # Run specific test file
uv run pytest -v                 # Verbose output
```

**Run tests before committing** to verify functionality.

### Documentation

After important changes or refactoring, update @README.md to keep it in sync with the code.

## Code Style & Philosophy

Follow these principles when writing or modifying code:

- **Simplicity over abstraction** - Prefer direct, straightforward code. Only introduce abstraction (DI, interfaces, etc.) when there's a concrete need (testing, multiple implementations, runtime swapping).

- **Readability is paramount** - Code will be read by junior developers. Write clear, explicit code over clever or terse code.

- **Ample comments** - Add more comments than typical. Explain _why_ decisions were made, especially when using third-party libraries. Less common libraries need more explanation.

- **Minimal exception handling** - Don't add excessive try/catch blocks initially. Focus on core functionality. Exception handling can be enhanced later if needed.

- **Minimal test coverage (for now)** - Write tests for core logic and major functions, but don't aim for 100% coverage. Code will likely be refactored. Test enough to catch major breaks.

## Project-Specific Conventions

### Environment Variables

Required variables must be documented in `.env.example`. Actual `.env` file contains secrets and is gitignored.

## Git & Version Control

- **Do NOT commit changes** unless explicitly asked by the user
- **Do NOT push to remote** unless explicitly instructed
- Check git status before making assumptions about repository state

### Branch Conventions

- `feature/` - New features
- `refactor/` - Code refactoring
- `fix/` - Bug fixes
- `docs/` - Documentation updates

**Always use `--no-ff` flag when merging** to preserve branch history:

```bash
git merge --no-ff feature/my-feature -m "Merge feature: description"
```

---

When in doubt, ask clarifying questions. The project is evolving rapidly and requirements may change.

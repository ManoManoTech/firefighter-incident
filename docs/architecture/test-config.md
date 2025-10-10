# Testing Configuration

## Test Environment Setup

### Required Environment Variables

```bash
export POSTGRES_DB=ff_dev
export POSTGRES_SCHEMA=
export PYTHONDEVMODE=1
export FF_SLACK_SKIP_CHECKS=true
export ENABLE_JIRA=true
export ENABLE_RAID=true
```

### Directory Structure

⚠️ **CRITICAL**: Always run tests from the `firefighter-oss/` directory, not from `impact/`

```text
impact/                           # Private GitLab repo
├── firefighter-oss/             # GitHub submodule (WORK HERE)
│   ├── src/firefighter/         # Source code
│   ├── tests/                   # Test files (REAL LOCATION)
│   └── pyproject.toml           # Test configuration
└── tests -> firefighter-oss/tests  # Symlink (DON'T USE)
```

## Standard Commands

### Core Test Commands

```bash
# Run all tests with coverage
POSTGRES_DB=ff_dev POSTGRES_SCHEMA= PYTHONDEVMODE=1 FF_SLACK_SKIP_CHECKS=true ENABLE_JIRA=true ENABLE_RAID=true pdm run pytest --cov=firefighter --cov-report=term-missing

# Run specific test file
POSTGRES_DB=ff_dev POSTGRES_SCHEMA= PYTHONDEVMODE=1 FF_SLACK_SKIP_CHECKS=true ENABLE_JIRA=true ENABLE_RAID=true pdm run pytest tests/test_raid/test_sync.py -v

# Run tests with HTML coverage report
POSTGRES_DB=ff_dev POSTGRES_SCHEMA= PYTHONDEVMODE=1 FF_SLACK_SKIP_CHECKS=true ENABLE_JIRA=true ENABLE_RAID=true pdm run pytest --cov=firefighter --cov-report=html --cov-report=term-missing

# Quick test run (no coverage, quiet)
POSTGRES_DB=ff_dev POSTGRES_SCHEMA= PYTHONDEVMODE=1 FF_SLACK_SKIP_CHECKS=true ENABLE_JIRA=true ENABLE_RAID=true pdm run pytest --tb=no -q
```

### Quality Assurance Commands

```bash
# Linting with Ruff
pdm run lint-ruff --output-format=github --exit-non-zero-on-fix

# Type checking with MyPy
pdm run lint-mypy

# Pre-commit hooks
pdm run pre-commit run --all-files

# Combined quality check
pdm run lint-ruff && pdm run lint-mypy && pdm run pre-commit run --all-files
```

## Test Structure

### Database Configuration

**Test Database**: PostgreSQL with isolated schema
**Transactions**: Each test runs in a transaction, rolled back after completion
**Factories**: Django factory_boy for test data generation

### Key Test Patterns

```python
import pytest
from django.test import override_settings
from unittest.mock import patch

@pytest.mark.django_db
class TestSyncLogic:
    def setup_method(self):
        # Test data setup using factories
        self.incident = IncidentFactory()

    @patch("module.function")
    @override_settings(ENABLE_RAID=True)
    def test_specific_behavior(self, mock_function):
        # Test implementation
        pass
```

### Factory Usage

```python
from firefighter.incidents.factories import (
    IncidentFactory,
    PriorityFactory,
    UserFactory,
)

# Create test data
incident = IncidentFactory(
    title="Test incident",
    priority=PriorityFactory(value=1)
)
```

## Coverage Configuration

### pyproject.toml Settings

```toml
[tool.coverage.run]
source = ["src"]
omit = [
    "*/tests/*",
    "*/migrations/*",
    "*/venv/*",
    "*/settings/*",
    "*/templates/*",  # HTML files excluded
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
]
```

### Current Coverage Targets

- **Global Target**: 60%+
- **Current Level**: ~51%
- **New Code**: 100% coverage required
- **Modified Files**: 100% coverage required

## Module-Specific Testing

### RAID Module

**Files**: `tests/test_raid/`
**Coverage**: 100% (achieved)
**Key areas**: Sync logic, JIRA client, webhooks, forms

```bash
# RAID-specific test run
POSTGRES_DB=ff_dev POSTGRES_SCHEMA= PYTHONDEVMODE=1 FF_SLACK_SKIP_CHECKS=true ENABLE_JIRA=true ENABLE_RAID=true pdm run pytest tests/test_raid/ -v
```

### Slack Integration

**Files**: `tests/test_slack/`
**Coverage**: Variable (20-80%)
**Challenges**: Complex mocking for Slack API

```bash
# Slack tests (requires extensive mocking)
POSTGRES_DB=ff_dev POSTGRES_SCHEMA= PYTHONDEVMODE=1 FF_SLACK_SKIP_CHECKS=true ENABLE_JIRA=true ENABLE_RAID=true pdm run pytest tests/test_slack/ -v
```

### Incident Management

**Files**: `tests/test_incidents/`
**Coverage**: 70-90%
**Focus**: Core business logic, models, views

## Common Testing Issues

### ImportError Solutions

**Problem**: `ImportError` when running tests
**Cause**: Running from wrong directory (impact/ instead of firefighter-oss/)
**Solution**: Always cd to firefighter-oss/ first

```bash
cd /Users/nicolas.lafitte/workspace/impact/firefighter-oss/
# Then run tests
```

### Database Issues

**Problem**: Test database connection failures
**Cause**: Missing environment variables
**Solution**: Use full environment variable prefix

```bash
env POSTGRES_DB=ff_dev POSTGRES_SCHEMA= PYTHONDEVMODE=1 FF_SLACK_SKIP_CHECKS=true ENABLE_JIRA=true ENABLE_RAID=true pdm run pytest
```

### Mock Configuration

**Common Mocks**:
- `@patch("firefighter.raid.sync.sync_incident_to_jira")`
- `@patch("firefighter.jira_app.client.JiraClient")`
- `@override_settings(ENABLE_RAID=True)`

## Performance Optimization

### Parallel Execution

```bash
# Run tests in parallel
pdm run pytest -n auto --dist=loadfile
```

### Selective Testing

```bash
# Test only modified files
pdm run pytest --lf  # Last failed
pdm run pytest --co  # Collect only (dry run)
```

### Database Optimization

- Use `@pytest.mark.django_db(transaction=True)` for complex tests
- Minimize database operations in setup
- Use `factory.create_batch()` for bulk data

## Debugging Tests

### Verbose Output

```bash
# Maximum verbosity
POSTGRES_DB=ff_dev POSTGRES_SCHEMA= PYTHONDEVMODE=1 FF_SLACK_SKIP_CHECKS=true ENABLE_JIRA=true ENABLE_RAID=true pdm run pytest -vvv --tb=long
```

### Specific Test Debugging

```bash
# Run single test with full traceback
POSTGRES_DB=ff_dev POSTGRES_SCHEMA= PYTHONDEVMODE=1 FF_SLACK_SKIP_CHECKS=true ENABLE_JIRA=true ENABLE_RAID=true pdm run pytest tests/test_raid/test_sync.py::TestClass::test_method -vvv --tb=long
```

### Coverage Debugging

```bash
# Coverage with missing line numbers
POSTGRES_DB=ff_dev POSTGRES_SCHEMA= PYTHONDEVMODE=1 FF_SLACK_SKIP_CHECKS=true ENABLE_JIRA=true ENABLE_RAID=true pdm run pytest --cov=firefighter.specific.module --cov-report=term-missing -v
```

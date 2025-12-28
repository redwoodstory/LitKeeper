# LitKeeper Testing Guide

## Overview

Comprehensive automated testing suite for the LitKeeper Flask application using pytest.

**Current Status:**
- ✅ 102 tests implemented
- ✅ 101 tests passing
- ✅ Security-critical functions tested (path traversal, filename sanitization)
- ✅ Validators fully tested
- 🚧 Additional unit, integration, and E2E tests to be implemented

## Test Structure

```
tests/
├── conftest.py              # Core fixtures (Flask app, temp dirs, mocks)
├── pytest.ini               # Pytest configuration
├── unit/                    # Fast isolated unit tests
│   ├── test_validators.py     # ✅ Pydantic validation (35 tests)
│   └── test_filename_sanitizer.py  # ✅ Security-critical sanitization (49 tests)
├── integration/             # Component interaction tests (TODO)
├── e2e/                     # Real HTTP request tests (TODO)
├── security/                # Security & penetration tests
│   └── test_path_traversal.py     # ✅ Directory traversal prevention (33 tests)
├── fixtures/                # Test data files
└── helpers/                 # Test utilities
    └── literotica_mocks.py # Mock HTML response generators
```

## Installation

Install test dependencies:

```bash
pip install -r requirements-dev.txt
```

Dependencies include:
- `pytest` - Testing framework
- `pytest-cov` - Coverage reporting
- `pytest-flask` - Flask test client fixtures
- `pytest-mock` - Mocking utilities
- `pytest-xdist` - Parallel test execution
- `pytest-timeout` - Timeout protection

## Running Tests

**Important:** Use `python -m pytest` instead of just `pytest` to ensure you're using the virtual environment's pytest.

### Run All Tests

```bash
python -m pytest
```

### Run Specific Test Categories

```bash
# Unit tests only
python -m pytest -m unit

# Security tests only
python -m pytest -m security

# Integration tests only
python -m pytest -m integration

# E2E tests only (once implemented)
python -m pytest -m e2e

# Run everything EXCEPT E2E (fast)
python -m pytest -m "not e2e"
```

### Run Specific Test Files

```bash
# Run filename sanitizer tests
python -m pytest tests/unit/test_filename_sanitizer.py

# Run validator tests
python -m pytest tests/unit/test_validators.py

# Run path traversal tests
python -m pytest tests/security/test_path_traversal.py
```

### Run with Verbose Output

```bash
python -m pytest -v
```

### Run in Parallel (Faster)

```bash
python -m pytest -n auto
```

### Generate Coverage Report

```bash
# Terminal report
python -m pytest --cov=app --cov-report=term-missing

# HTML report (opens in browser)
python -m pytest --cov=app --cov-report=html
open htmlcov/index.html

# Both terminal and HTML
python -m pytest --cov=app --cov-report=term-missing --cov-report=html
```

## Test Markers

Tests are organized using pytest markers:

- `@pytest.mark.unit` - Fast unit tests with no external dependencies
- `@pytest.mark.integration` - Integration tests using Flask test client
- `@pytest.mark.e2e` - End-to-end tests with real HTTP requests (slow)
- `@pytest.mark.security` - Security and penetration tests
- `@pytest.mark.slow` - Slow-running tests (real downloads, rate limiting)

## Coverage Goals

| Component | Target Coverage | Current Status |
|-----------|----------------|----------------|
| **Overall** | 80% | 🚧 In progress |
| **Security-critical** | 100% | ✅ filename.py, validators.py |
| **Services** | 85% | 🚧 To implement |
| **Routes** | 90% | 🚧 To implement |

## Implemented Tests

### ✅ Unit Tests: Validators (35 tests)

- `test_validators.py` - Comprehensive Pydantic validation testing
  - StoryDownloadRequest validation (URL, formats, wait parameter)
  - LibraryFilterRequest validation (search, category, view)
  - Edge cases: empty inputs, special characters, Unicode

### ✅ Unit Tests: Filename Sanitizer (49 tests)

- `test_filename_sanitizer.py` - **Security-critical** sanitization tests
  - Path traversal prevention (`../`, `..\\`, absolute paths)
  - Special character removal (`<>:"/\|?*`)
  - Command injection prevention (`;`, `|`, `&`, `$()`)
  - Null byte injection prevention
  - Unicode and emoji handling
  - Leading/trailing dot handling

### ✅ Security Tests: Path Traversal (33 tests)

- `test_path_traversal.py` - Directory traversal attack prevention
  - Download route (`/download/<filename>`) - 11 tests
  - Read route (`/read/<filename>`) - 8 tests
  - Cover route (`/api/cover/<filename>`) - 9 tests
  - Advanced vectors (null bytes, Unicode, encoded) - 5 tests

## Pending Tests (To Be Implemented)

### Unit Tests (TODO)

- `test_epub_generator.py` - EPUB creation logic
- `test_html_generator.py` - HTML/JSON generation
- `test_cover_generator.py` - PIL cover image generation
- `test_logger.py` - Rotating file handlers
- `test_notifier.py` - Apprise notifications
- `test_utils.py` - Path utilities

### Integration Tests (TODO)

- `test_api_routes.py` - API endpoints (/api/download, /api/library, /api/cover)
- `test_library_routes.py` - Library UI (/, /library/filter, /read)
- `test_download_routes.py` - File downloads (/download/<file>)
- `test_story_processor.py` - Orchestration layer

### E2E Tests (TODO)

- `test_real_download.py` - Real Literotica downloads with rate limiting
- `test_series_detection.py` - Multi-chapter series following
- `test_full_workflow.py` - Complete URL → EPUB/HTML workflow

### Security Tests (TODO)

- `test_malicious_input.py` - XSS, SQL injection, template injection
- `test_encoding_issues.py` - Unicode, encoding edge cases

## Test Fixtures

### Flask App Fixture

The `app` fixture in `conftest.py` provides:
- Flask app with test configuration
- Temporary data directories (epubs, html, covers, logs)
- Mocked path utilities
- Disabled logging and notifications

### Sample Data Fixtures

- `sample_story_content` - Multi-chapter story text
- `sample_literotica_html` - Mocked Literotica HTML response
- `test_data_dir` - Path to fixtures directory
- `temp_dir` - Temporary filesystem for file operations

### Mock Helpers

`tests/helpers/literotica_mocks.py` provides:
- `create_mock_literotica_response()` - Generate custom HTML responses
- `create_mock_multipage_story()` - Multi-page story with pagination
- `create_mock_series()` - Multi-chapter series with continuation links

## CI/CD Integration (Not Configured)

This test suite is designed for local testing only. To add CI/CD:

1. Create `.github/workflows/test.yml`
2. Run `pytest -m "not e2e"` to skip slow E2E tests
3. Upload coverage reports to Codecov or similar

## Troubleshooting

### Tests Fail Due to Missing Dependencies

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

### Coverage Below 80%

This is expected during implementation. To run without coverage enforcement:

```bash
pytest --no-cov
```

Or adjust coverage threshold in `pytest.ini`.

### Resource Warnings

Some tests may show `ResourceWarning: unclosed file` - these are minor issues in the application code, not test failures.

## Contributing

When adding new tests:

1. Place in appropriate directory (`unit/`, `integration/`, `e2e/`, `security/`)
2. Add appropriate markers (`@pytest.mark.unit`, etc.)
3. Use existing fixtures from `conftest.py`
4. Follow naming convention: `test_<functionality>.py`
5. Run tests locally before committing

## Questions?

- Check existing tests for examples
- Review pytest documentation: https://docs.pytest.org/
- Review Flask testing docs: https://flask.palletsprojects.com/en/latest/testing/

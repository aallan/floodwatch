# Contributing to Floodwatch

Thanks for your interest in contributing to Floodwatch! This document explains how to get involved.

## Reporting Bugs

Open an issue on GitHub using the **Bug report** template. Include:

- What you expected to happen
- What actually happened
- Steps to reproduce (if possible)
- Browser and OS version (for frontend issues)
- Python version (for backend issues)

## Suggesting Features

Open an issue using the **Feature request** template. Describe the problem you're trying to solve and any ideas you have for a solution.

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/aallan/floodwatch.git
   cd floodwatch
   ```

2. Fetch historical data:
   ```bash
   python fetch_data.py --recent    # Quick — last 2 days
   ```

3. Start the dev server:
   ```bash
   python serve.py
   open http://localhost:8080
   ```

4. Install test dependencies:
   ```bash
   pip install pytest               # Python tests
   cd js-tests && npm install       # JavaScript tests
   ```

## Running Tests

```bash
pytest tests/ -v                    # 55 Python tests
cd js-tests && npm test             # 25 JavaScript tests
```

All tests must pass before a pull request can be merged. See [TESTING.md](TESTING.md) for details on what each test covers.

## Submitting a Pull Request

1. Fork the repo and create a branch from `main`:
   ```bash
   git checkout -b my-feature main
   ```

2. Make your changes. Follow the existing code style:
   - **Python:** 4-space indentation, no type hints required (but welcome)
   - **JavaScript:** 2-space indentation, single quotes
   - **HTML/CSS:** inline in `index.html` (single-page app)

3. Add or update tests if your change affects the data pipeline, server logic, or frontend utility functions.

4. Run the test suite and make sure everything passes.

5. Commit with a clear message describing what changed and why:
   ```bash
   git commit -m "Add support for additional rainfall stations"
   ```

6. Push and open a pull request against `main`.

## What We're Looking For

Contributions that improve:

- **Data accuracy** — better handling of EA API edge cases, missing readings, or unit mismatches
- **Performance** — faster data loading, smarter caching, smaller payload sizes
- **Accessibility** — screen reader support, keyboard navigation, colour contrast
- **Mobile experience** — better touch interactions, responsive layout improvements
- **Documentation** — clearer explanations, typo fixes, additional deployment guides
- **Test coverage** — more edge cases, integration tests, or new test fixtures

## What to Avoid

- Don't add build tools or transpilers — the frontend is deliberately vanilla HTML/CSS/JS
- Don't add Python dependencies beyond pytest — the backend uses only the standard library
- Don't commit changes to CSV data files — these are updated automatically by GitHub Actions

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to uphold this code.

## Questions?

Open a discussion or issue on GitHub. There are no silly questions.

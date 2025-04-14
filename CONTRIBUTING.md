# Contributing to AsyncWebOSTV

Thank you for your interest in contributing to AsyncWebOSTV! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

By participating in this project, you agree to abide by our Code of Conduct. Please be respectful and considerate of others.

## How to Contribute

1. **Fork the Repository**
   - Click the "Fork" button on the GitHub repository page
   - Clone your forked repository to your local machine

2. **Create a Branch**
   - Create a new branch for your feature or bugfix
   - Use a descriptive name (e.g., `feature/add-new-control` or `fix/connection-error`)

3. **Make Changes**
   - Write your code following the project's style guidelines
   - Add tests for new features or bugfixes
   - Update documentation as needed

4. **Commit Changes**
   - Write clear, descriptive commit messages
   - Reference any related issues in your commit messages

5. **Push Changes**
   - Push your branch to your forked repository

6. **Create a Pull Request**
   - Open a pull request from your branch to the main repository
   - Provide a clear description of your changes
   - Reference any related issues

## Development Setup

1. Install development dependencies:
```bash
pip install -e ".[dev]"
```

2. Run tests:
```bash
pytest
```

3. Format code:
```bash
black .
isort .
```

4. Check types:
```bash
mypy .
```

## Code Style

- Follow PEP 8 guidelines
- Use type hints for all function parameters and return values
- Write docstrings for all public functions and classes
- Keep functions focused and small
- Write tests for new features and bugfixes

## Testing

- Write tests for all new features and bugfixes
- Ensure all tests pass before submitting a pull request
- Use pytest for testing
- Follow the existing test patterns

## Documentation

- Update documentation for any new features or changes
- Keep docstrings up to date
- Add examples for new features

## Questions?

If you have any questions, feel free to open an issue or contact the maintainers. 
# Contributing to GraphRouter

First off, thank you for considering contributing to GraphRouter! It's people like you that make GraphRouter such a great tool.

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## How Can I Contribute?

### Reporting Bugs

This section guides you through submitting a bug report for GraphRouter. Following these guidelines helps maintainers and the community understand your report, reproduce the behavior, and find related reports.

**Before Submitting A Bug Report**

* Check the [documentation](docs/README.md) for a list of common questions and problems.
* Ensure the bug was not already reported by searching on GitHub under [Issues](https://github.com/graphrouter/graphrouter/issues).

**How Do I Submit A (Good) Bug Report?**

Bugs are tracked as GitHub issues. Create an issue using our [bug report template](https://github.com/graphrouter/graphrouter/issues/new?template=bug_report.md) and provide the following information:

* Use a clear and descriptive title
* Describe the exact steps which reproduce the problem
* Provide specific examples to demonstrate the steps
* Describe the behavior you observed after following the steps
* Explain which behavior you expected to see instead and why
* Include details about your configuration and environment

### Suggesting Enhancements

This section guides you through submitting an enhancement suggestion for GraphRouter, including completely new features and minor improvements to existing functionality.

**Before Submitting An Enhancement Suggestion**

* Check if the enhancement has already been suggested
* Check the [documentation](docs/README.md) to see if the functionality exists
* Search the [issues list](https://github.com/graphrouter/graphrouter/issues) for existing suggestions

### Pull Requests

* Fill in the required [pull request template](.github/pull_request_template.md)
* Do not include issue numbers in the PR title
* Include screenshots and animated GIFs in your pull request whenever possible
* Follow the Python styleguide
* Include thoughtfully-worded, well-structured tests
* Document new code
* End all files with a newline

## Development Process

1. Fork the repo
2. Create a new branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run the tests
5. Commit your changes (`git commit -m 'Add some amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Setup Development Environment

```bash
# Clone your fork
git clone https://github.com/graphrouter/graphrouter.git
cd graphrouter

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

### Code Style

* Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
* Use meaningful variable names
* Comment your code when necessary
* Add type hints to function definitions
* Keep functions focused and small

## Testing

* Write unit tests for new features
* Ensure all tests pass before submitting PR
* Include integration tests when appropriate
* Test different database backends

## Documentation

* Update the documentation with any changes
* Include docstrings for new functions
* Add examples for new features
* Keep README.md updated

Thank you for contributing to GraphRouter!
# Contributing to Imagen MCP Server

First off, thank you for considering contributing to Imagen MCP Server! 🎉

This document provides guidelines and best practices for contributing to this project. Following these guidelines helps communicate that you respect the time of the developers managing and developing this open source project.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [How Can I Contribute?](#how-can-i-contribute)
  - [Reporting Bugs](#-reporting-bugs)
  - [Suggesting Features](#-suggesting-features)
  - [Pull Requests](#-pull-requests)
- [Development Setup](#development-setup)
- [Style Guidelines](#style-guidelines)
- [Commit Messages](#commit-messages)
- [MCP Server Development Guidelines](#mcp-server-development-guidelines)

## Code of Conduct

This project and everyone participating in it is governed by our commitment to providing a welcoming and inclusive environment. By participating, you are expected to:

- Use welcoming and inclusive language
- Be respectful of differing viewpoints and experiences
- Gracefully accept constructive criticism
- Focus on what is best for the community
- Show empathy towards other community members

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/your-username/imagen-mcp.git
   cd imagen-mcp
   ```
3. **Set up the development environment** (see [Development Setup](#development-setup))
4. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## How Can I Contribute?

### 🐛 Reporting Bugs

Before creating bug reports, please check existing issues to avoid duplicates.

**When creating a bug report, include:**

- **Clear title** describing the issue
- **Environment details**: Python version, OS, MCP client being used
- **Steps to reproduce** the behavior
- **Expected behavior** vs. **actual behavior**
- **Error messages** or logs (redact any API keys!)
- **Screenshots** if applicable

**Bug Report Template:**

```markdown
## Bug Description
A clear and concise description of the bug.

## Environment
- OS: [e.g., macOS 14.0, Windows 11, Ubuntu 22.04]
- Python Version: [e.g., 3.11.5]
- MCP Client: [e.g., Claude Desktop, VS Code Copilot]
- Package Version: [output of `pip show fastmcp`]

## Steps to Reproduce
1. Go to '...'
2. Run '...'
3. See error

## Expected Behavior
What you expected to happen.

## Actual Behavior
What actually happened.

## Logs/Error Messages
```
Paste relevant logs here
```

## Additional Context
Any other context about the problem.
```

### 💡 Suggesting Features

Feature suggestions are welcome! Please provide:

- **Use case**: Why is this feature needed?
- **Proposed solution**: How should it work?
- **Alternatives considered**: Other ways to solve the problem
- **Impact**: How would this benefit other users?

**Feature Request Template:**

```markdown
## Feature Description
A clear and concise description of the feature.

## Use Case
Describe the problem this feature would solve.

## Proposed Solution
Describe how you'd like this feature to work.

## Alternatives Considered
Describe any alternative solutions you've considered.

## Additional Context
Any other context, mockups, or examples.
```

### 🔧 Pull Requests

1. **Ensure your PR addresses an existing issue** or create one first
2. **Follow the style guidelines** outlined below
3. **Include tests** for new functionality
4. **Update documentation** as needed
5. **Keep PRs focused** - one feature or fix per PR

**Pull Request Process:**

1. Update the README.md if the change affects usage
2. Update docstrings for any modified functions
3. Ensure all tests pass
4. Request review from maintainers

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Git
- A Google AI API key (for testing)

### Setup Steps

1. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install development dependencies:**
   ```bash
   pip install pytest pytest-asyncio black ruff mypy
   ```

4. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your Google AI API key (GOOGLE_AI_API_KEY)
   ```

5. **Run the server locally:**
   ```bash
   python run_server.py
   ```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=imagen_mcp

# Run specific test file
pytest tests/test_core.py
```

### Code Formatting

```bash
# Format code with Black
black .

# Check linting with Ruff
ruff check .

# Type checking with MyPy
mypy imagen_mcp/
```

## Style Guidelines

### Python Style

- Follow [PEP 8](https://pep8.org/) style guide
- Use [Black](https://black.readthedocs.io/) for formatting
- Use [Ruff](https://docs.astral.sh/ruff/) for linting
- Maximum line length: 100 characters
- Use type hints for all function signatures

### Documentation

- All public functions must have docstrings (Google style)
- Include parameter descriptions and return types
- Add usage examples for complex functions

**Example Docstring:**

```python
def generate_image(
    *,
    prompt: str,
    aspect_ratio: Optional[str] = None,
) -> ImageResult:
    """Generate an image using the Gemini API.
    
    Args:
        prompt: Text description of the image to generate.
        aspect_ratio: Optional aspect ratio (e.g., "1:1", "16:9").
    
    Returns:
        ImageResult containing the image buffer and metadata.
    
    Raises:
        ValueError: If prompt is empty or invalid.
        RuntimeError: If API request fails.
    
    Example:
        >>> result = generate_image(prompt="A sunset over mountains")
        >>> print(f"Generated {len(result.buffer)} bytes")
    """
```

### MCP Tool Guidelines

When adding or modifying MCP tools:

- **Clear descriptions**: Tool descriptions should explain what the tool does
- **Parameter validation**: Validate all inputs before processing
- **Error handling**: Return structured error responses, don't raise exceptions
- **Consistent return format**: Use consistent dictionary structure for responses

```python
@mcp.tool()
def my_new_tool(param: str) -> dict:
    """Clear, concise description of what this tool does.
    
    Args:
        param: Description of the parameter.
    
    Returns:
        A dictionary containing success status and relevant data.
    """
    try:
        # Implementation
        return {
            "success": True,
            "data": result,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
```

## Commit Messages

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

### Examples

```
feat(tools): add image editing capability

fix(core): handle API timeout gracefully

docs(readme): add Claude Desktop configuration example

test(server): add unit tests for generate_image tool
```

## MCP Server Development Guidelines

### Protocol Compliance

- Follow the [MCP Specification](https://modelcontextprotocol.io/specification)
- Use stdio transport for broad compatibility
- Implement proper capability negotiation

### Tool Design Principles

1. **Single Responsibility**: Each tool should do one thing well
2. **Idempotency**: Tools should be safe to retry
3. **Descriptive Names**: Tool names should clearly indicate their purpose
4. **Comprehensive Descriptions**: Descriptions help AI assistants use tools effectively

### Error Handling

- Never let exceptions propagate to the MCP client unhandled
- Return structured error responses with helpful messages
- Log errors for debugging (use `console.error` for stdio servers)

### Security Considerations

- Never log or expose API keys
- Validate file paths to prevent directory traversal
- Rate limit API calls to prevent abuse
- Sanitize user inputs

## Questions?

Feel free to:
- Open a [GitHub Discussion](https://github.com/yourusername/imagen-mcp/discussions)
- Reach out to the maintainers

---

Thank you for contributing! 🙏

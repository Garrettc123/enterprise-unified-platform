# Contributing to Enterprise Unified Platform

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/enterprise-unified-platform.git`
3. Create a feature branch: `git checkout -b feature/your-feature`
4. Follow the development guide in DEVELOPMENT.md

## Code Standards

### Python
- Follow PEP 8
- Use type hints
- Write docstrings for functions
- Use meaningful variable names
- Maximum line length: 100 characters

### TypeScript/React
- Use functional components with hooks
- Add prop types
- Follow React naming conventions
- Use semantic HTML
- Maintain consistent code formatting

### General
- Write clear commit messages
- Add tests for new features
- Update documentation
- Keep commits atomic and focused

## Pull Request Process

1. **Before submitting:**
   - Run tests: `pytest backend/tests/`
   - Run linting: `flake8 backend/`
   - Format code: `black backend/`
   - Build frontend: `npm run build`

2. **Create PR with:**
   - Descriptive title
   - Clear description of changes
   - Reference related issues
   - Screenshots for UI changes

3. **Review process:**
   - Address reviewer feedback
   - Keep commits clean and organized
   - Rebase if needed
   - Wait for approval before merging

## Reporting Issues

1. Check existing issues first
2. Include:
   - Clear description
   - Steps to reproduce
   - Expected behavior
   - Actual behavior
   - Screenshots if applicable
   - Environment details

## Feature Requests

1. Describe the desired functionality
2. Explain the use case
3. Provide examples
4. Discuss alternatives

## Community

- Be respectful and inclusive
- Follow code of conduct
- Help others in discussions
- Share knowledge and experiences

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

# Security Policy

## Reporting Security Vulnerabilities

If you discover a security vulnerability in release-radar, please report it responsibly by creating a GitHub issue or contacting the maintainers. Avoid disclosing security issues publicly until they have been addressed.

## Security Best Practices

### Secrets Management
- Never commit secrets, API keys, or credentials to version control.
- Use environment variables for all sensitive configuration.
- Store secrets in your deployment platform's secret management system (e.g., GitHub Secrets for CI, Kubernetes Secrets for production).
- `.env` files, certificates (`*.key`, `*.pem`, `*.p12`), and secret directories (`secrets/`, `config/secrets.yml`) are ignored by git.

### Dependency Security
- We use Dependabot for automated dependency updates.
- Run security audits regularly (`pip-audit` for Python dependencies, `npm audit` for Node dependencies if applicable).
- Pin production dependencies to specific versions.

### Application Security
- All user inputs should be validated and sanitized.
- Database queries must use parameterized queries to prevent SQL injection.
- Implement rate limiting on API endpoints.
- Configure CORS appropriately for your deployment.
- Use proper authentication and authorization where applicable.
- Do not leak sensitive information in error messages or logs.

### Infrastructure Security
- Use HTTPS everywhere in production.
- Configure security headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy).
- Apply security patches promptly.
- Follow the principle of least privilege for all access.

## Supported Versions

We currently provide security updates for the latest main branch.

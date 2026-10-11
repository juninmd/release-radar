# Security Audit Report

## Date
2026-10-11

## Scope
Repository: juninmd/release-radar

## Summary
Initial security review of the release-radar codebase. The following items were assessed: secrets management, dependency security, code security (SQL injection, input validation, error handling), CI/CD security, and infrastructure security.

## Findings

### 1. Secrets Management ✅
- `.gitignore` now includes comprehensive patterns: `.env`, `.env.local`, `.env.*.local`, `.key`, `.pem`, `.p12`, `secrets/`, `config/secrets.yml`.
- Secrets are loaded via environment variables using `pydantic-settings` (`config.py`).
- Database credentials and API keys are passed via environment/config; no hardcoded secrets found.
- CI workflows use GitHub Secrets appropriately.

### 2. Dependency Security ✅
- `dependabot.yml` added for automated pip dependency updates (weekly).
- `pip-audit` run; project dependencies audited (pr-assistant in environment is external, not in repo).
- Dependencies pinned in `pyproject.toml` with version constraints.

### 3. Code Security
- **SQL Injection**: ✅ All database queries use parameterized queries (`%s` with psycopg2) - verified in `db.py`, `web.py` queries.
- **Input Validation**: CLI validates positive integers via `positive_int()` function. RSS feed parsing validates URLs, rejects DOCTYPE entities (XXE protection via DOCTYPE rejection and size limits). 
- **Error Handling**: Web API returns generic error messages without leaking internal details (`test_database_failure_returns_generic_error_without_connection_details`).
- **Path Traversal**: Web server serves only specific files from STATIC dir with exact paths in `FILES` mapping; unknown paths return 404.
- **XXE Protection**: RSS parser rejects feeds declaring DOCTYPE (`_DOCTYPE_SCAN_BYTES` check, `ValueError` if DOCTYPE detected) - good defense against entity expansion attacks.
- **Resource Exhaustion**: RSS parser enforces max feed size (8MB) and streams to avoid buffering entire body.
- **Security Headers**: Web server sets `X-Content-Type-Options: nosniff` and Content-Security-Policy with restrictive defaults including `frame-ancestors 'none'`, `base-uri 'none'`.

### 4. CI/CD Security ✅
- No scheduled (`cron`) triggers in workflows - build.yml only on PR, docker.yml only on push to main.
- Workflows use pinned action SHAs where observed (`actions/checkout@11d596...`, `astral-sh/setup-uv@c18668...`).
- Least privilege permissions applied in docker.yml (`contents: read`, `packages: write`).
- No secrets committed; uses `${{ secrets.GITHUB_TOKEN }}` appropriately.
- Follows policy: no GitHub Actions scheduled jobs.

### 5. Infrastructure Security
- Default web server binds to `127.0.0.1` (localhost only); CLI warns about remote binding.
- HTTPS recommended in production (docs updated in SECURITY.md).
- Security headers implemented in web server.

## Recommendations
- Consider adding rate limiting middleware for web API endpoints if exposed beyond localhost.
- Consider CORS configuration if API consumed by other origins.
- Add security scanning (SAST) to CI pipeline - e.g., bandit, semgrep (can be added as optional step).
- Review dependency updates from Dependabot regularly.

## Compliance
- OWASP Top 10: Key items addressed (injection via parameterized queries, XXE via DTD rejection, security misconfiguration via headers, sensitive data exposure via generic errors, broken access control considerations with localhost binding).


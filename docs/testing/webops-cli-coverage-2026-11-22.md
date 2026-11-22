# WebOps CLI — 100% statement coverage verification

**Date:** 2026-11-22  
**Scope:** `cli/webops_cli/` on Python 3.11, tested on Runpod CPU  
**Coverage type:** executable Python statement/line coverage (not branch coverage)  
**Acceptance gate:** 100% (required in `cli/pyproject.toml` and CI)

## Measured result

| Metric | Verified |
| --- | ---: |
| Statements counted by coverage.py | 5,083 |
| Statements executed by tests | 5,083 |
| Missing statements | 0 |
| Statement coverage | **100.00%** |
| Tests passed | **3,173** |
| Pytest subtests passed | **41** |
| Test execution time (final run) | 7.77 seconds |
| Final test process exit code | 0 |
| Existing excluded source statements | 11 |

No additional source exclusion rules, `# pragma: no cover` directives, or lowered coverage thresholds were introduced to obtain this result. This statement metric follows the project's existing `coverage.py` configuration.

The original baseline before this programme was **32.31%** from **2,042 tests**. Tests were expanded for Django/deployment/setup/troubleshooting wizards, database and Celery diagnostics, service operations, terminal UI, configuration recovery, encryption and secrets, API authentication and token refresh, WebSocket reconnection, input validation, privileged admin controls, GitHub project setup, AI-assisted deployment, and concurrency/fault-injection primitives.

## Reproduce

```bash
cd cli
python -m pip install -e . pytest pytest-cov pytest-asyncio
python -m pytest -q tests/
python -m coverage report --fail-under=100
```

Default `pytest` now fails when measured total statement coverage is below 100%. No `-o addopts=` or coverage overrides are required. The dedicated GitHub Actions workflow `.github/workflows/cli-coverage.yml` runs the same gate on changes to `cli/`, including pushes to `main`. `.github/workflows/pr-checks.yml` also fails rather than warning if CLI statement coverage falls below 100%.

## Correctness issues discovered and repaired

- Corrupt configuration could recurse while attempting automatic backup cleanup. Recovery now reads retention settings without recursively loading config, with regression coverage.
- Interactive setup rejected Python 3.11 despite published support; corrected the minimum version check and test.
- Troubleshooting CLI imported `psutil` without declaring it; added it to the runtime dependency manifests.
- Deployment wizard rejected ordinary nested subdomains; corrected the domain rule.
- Shortcut deployment creation passed the wrong request shape and deployment-list display treated a response mapping as a sequence; aligned them to the API contracts.
- Legacy environment-set-with-restart referenced an undefined deployment variable and printed environment values that could contain secrets; both corrected.
- Project setup success/failure audit referenced an undefined logger; replaced with an existing structured deployment audit event.
- Legacy duplicate `deploy` command definition was unreachable, so it was removed in favor of the single governed `webops deploy`.
- GitHub SSH URL normalization now maps recognized GitHub remotes to canonical HTTPS without producing malformed clone URLs.
- Admin's `inactive` service label was styled as healthy because the substring `active` matched first; corrected condition ordering.
- Redundant unreachable domain checks and unreachable best-settings fallback were simplified without weakening the existing strict input pattern.
- WebSocket recoverable failures now have direct retry/backoff tests.

## Important interpretation

**100% statement coverage does not prove 100% behavior or branch coverage.** Concurrency tests, simulated transport faults and unit fixtures are not a replacement for production-like load, remote provider tests, Docker hosting acceptance, multi-process resilience, disaster recovery, or security auditing. Several legacy wizard flows simulate installation/deployment phases; exercising those branches does not turn them into live service verification.

For the remaining production and end-to-end integration gates, see [Ifinsta E2E verification](webops-resilience-jani-e2e-2026-11-22.md).


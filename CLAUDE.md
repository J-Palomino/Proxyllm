# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Proxyllm is a customized fork of LiteLLM v1.80.7 with enterprise features for:
- **Stripe billing integration** - Prepaid credits, metered billing, and subscriptions
- **Railway deployment** - Production infrastructure with health checks
- **Tailscale VPN** - Secure access to on-premises Ollama instances (hugo:11434)

## Development Commands

### Installation
```bash
make install-dev           # Core development dependencies
make install-proxy-dev     # Full proxy development (includes --extras proxy)
make install-test-deps     # All test dependencies (includes enterprise)
make install-dev-ci        # CI-compatible (pins OpenAI==2.8.0)
```

### Testing
```bash
make test                  # Run all tests
make test-unit             # Unit tests with 4 parallel workers (-x -vv -n 4)
make test-integration      # Integration tests (excludes test_litellm/)

# Run specific tests
poetry run pytest tests/test_litellm/test_utils.py -v
poetry run pytest tests/test_litellm/test_utils.py::test_function_name -v
poetry run pytest tests/llm_translation/test_openai.py --timeout=300
```

### Code Quality
```bash
make lint                  # All checks (matches CI exactly)
make format                # Apply Black formatting
make format-check          # Check formatting only (no auto-fix)
make lint-ruff             # Ruff linting only
make lint-mypy             # MyPy type checking only
make check-circular-imports
make check-import-safety
```

### Running the Proxy Server Locally
```bash
poetry run litellm --config proxy_server_config.yaml --port 4000
# Or with docker-compose (includes PostgreSQL + Prometheus)
docker-compose up
```

## Architecture Overview

LiteLLM is a unified interface for 100+ LLM providers with two main components:

### Core Library (`litellm/`)
- `main.py` - Core completion(), acompletion(), embedding() entry points
- `llms/` - Provider implementations (each in own subdirectory: `openai/`, `anthropic/`, `bedrock/`, etc.)
- `router.py` + `router_utils/` - Load balancing, fallback logic, routing strategies
- `types/` - Pydantic v2 models for all API contracts
- `integrations/` - Observability (Datadog, Langfuse, etc.), caching, logging
- `caching/` - Cache backends (Redis, in-memory, S3, DiskCache)
- `secret_managers/` - Azure KMS, Google Cloud KMS, AWS Secrets Manager

### Proxy Server (`litellm/proxy/`)
- `proxy_server.py` - FastAPI application (port 4000 default)
- `auth/` - API key auth, JWT, OAuth2, SSO
- `db/` - Prisma ORM with PostgreSQL/SQLite
- `management_endpoints/` - Admin APIs for keys, teams, models, budgets
- `pass_through_endpoints/` - Provider-specific API forwarding
- `guardrails/` - Content filtering and safety hooks
- `health_check.py` - Health monitoring endpoints
- `_experimental/out/` - Admin UI dashboard (Next.js build, served at `/ui`)

### Custom Proxyllm Additions
- **Stripe billing**: `management_endpoints/stripe_balance_endpoints.py`, `stripe_meter_endpoints.py`
- **Railway deployment**: `Dockerfile.railway`, `railway.toml`, `proxy_server_config.railway.yaml`
- **Custom DB tables**: `LiteLLM_StripeBalanceTable`, `LiteLLM_StripeTransactionTable`

## Key Patterns

### Provider Implementation
- Providers inherit from base classes in `litellm/llms/base.py`
- Each provider has transformation classes (e.g., `OpenAIConfig`, `AnthropicConfig`)
- Must support both sync and async operations
- Handle streaming responses and function/tool calling
- See `litellm/llms/anthropic/chat/transformation.py` for complex tool handling example

### Error Handling
- Provider-specific exceptions mapped to OpenAI-compatible errors
- Fallback logic handled by Router system with configurable strategies
- Logging through `litellm/_logging.py`

### Configuration
- YAML config files for proxy (see `litellm/proxy/example_config_yaml/`)
- Environment variables for API keys
- Database schema via Prisma (`schema.prisma` in root)
- Migrations: `prisma migrate dev`

## Stripe Billing Integration

Three billing methods supported:
1. **Billing Meters** - Real-time usage via Stripe Billing Meters API
2. **Subscriptions** - Recurring billing
3. **Prepaid Credits** - Users pre-pay, usage deducts from balance

Key endpoints:
- `GET /stripe/balance` - Check prepaid balance
- `POST /stripe/topup` - Create Stripe Checkout Session
- `GET /stripe/transactions` - View transaction history
- `POST /stripe/webhook` - Stripe webhook handler

Environment variables: `STRIPE_API_KEY`, `STRIPE_METER_EVENT_NAME`, `STRIPE_USE_PREPAID_BALANCE`

## Railway Deployment

Architecture: Client APIs -> Railway (LiteLLM Proxy) -> Tailscale VPN -> hugo:11434 (Ollama)

Key files:
- `Dockerfile.railway` - Multi-stage build with Tailscale
- `railway.toml` - Railway platform configuration
- `proxy_server_config.railway.yaml` - Production proxy config

Environment variables for Railway:
- `TAILSCALE_AUTH_KEY` - Auth key tagged with `railway-proxy`
- `LITELLM_MASTER_KEY` - Master API key
- `TAILSCALE_ADVERTISE_ROUTES` - Optional subnet routing
- `TAILSCALE_ACCEPT_ROUTES` - Accept routes from other nodes

## Test Structure

Tests mirror the `litellm/` directory structure:
- `tests/test_litellm/` - Unit tests (mocked, no real API calls) - **required for PRs**
- `tests/llm_translation/` - Provider integration tests (real APIs)
- `tests/proxy_unit_tests/` - Proxy server tests
- `tests/load_tests/` - Performance testing

File naming: `litellm/proxy/foo.py` -> `tests/test_litellm/proxy/test_foo.py`

## Development Notes

### Code Style
- Black formatter (120 char line length)
- Ruff linter
- MyPy type checker
- Pydantic v2 for data validation
- Follows Google Python Style Guide

### PR Requirements
- Sign CLA before contributing
- Add at least 1 test in `tests/test_litellm/`
- Pass `make lint` and `make test-unit`
- Keep scope isolated (one feature/fix per PR)

### Enterprise Features
- Enterprise code in `enterprise/` directory
- Optional features via environment variables

## Related Documentation

- `RAILWAY_DEPLOYMENT.md` - Railway deployment guide
- `STRIPE_PREPAID_SETUP.md` - Stripe billing setup
- `TAILSCALE_SUBNET_ROUTING.md` - VPN configuration
- `AGENTS.md` - Agent development instructions
- `CONTRIBUTING.md` - Full contribution guidelines

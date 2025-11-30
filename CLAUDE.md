# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Proxyllm is a customized fork of LiteLLM with enterprise features for:
- **Stripe billing integration** - Prepaid credits, metered billing, and subscriptions
- **Railway deployment** - Production infrastructure with health checks
- **Tailscale VPN** - Secure access to on-premises Ollama instances (hugo:11434)

## Development Commands

### Installation
- `make install-dev` - Install core development dependencies
- `make install-proxy-dev` - Install proxy development dependencies with full feature set
- `make install-test-deps` - Install all test dependencies

### Testing
- `make test` - Run all tests
- `make test-unit` - Run unit tests (tests/test_litellm) with 4 parallel workers
- `make test-integration` - Run integration tests (excludes unit tests)
- `poetry run pytest tests/path/to/test_file.py -v` - Run specific test file
- `poetry run pytest tests/path/to/test_file.py::test_function -v` - Run specific test

### Code Quality
- `make lint` - Run all linting (Ruff, MyPy, Black, circular imports, import safety)
- `make format` - Apply Black code formatting
- `make lint-ruff` - Run Ruff linting only
- `make lint-mypy` - Run MyPy type checking only

## Architecture Overview

LiteLLM is a unified interface for 100+ LLM providers with two main components:

### Core Library (`litellm/`)
- **Main entry point**: `litellm/main.py` - Core completion() function
- **Provider implementations**: `litellm/llms/` - Each provider has its own subdirectory
- **Router system**: `litellm/router.py` + `litellm/router_utils/` - Load balancing and fallback logic
- **Type definitions**: `litellm/types/` - Pydantic models and type hints
- **Integrations**: `litellm/integrations/` - Third-party observability, caching, logging
- **Caching**: `litellm/caching/` - Multiple cache backends (Redis, in-memory, S3, etc.)

### Proxy Server (`litellm/proxy/`)
- **Main server**: `proxy_server.py` - FastAPI application
- **Authentication**: `auth/` - API key management, JWT, OAuth2
- **Database**: `db/` - Prisma ORM with PostgreSQL/SQLite support
- **Management endpoints**: `management_endpoints/` - Admin APIs for keys, teams, models
- **Pass-through endpoints**: `pass_through_endpoints/` - Provider-specific API forwarding
- **Guardrails**: `guardrails/` - Safety and content filtering hooks
- **UI Dashboard**: Served from `_experimental/out/` (Next.js build)

### Custom Additions (Proxyllm-specific)
- **Stripe endpoints**: `litellm/proxy/management_endpoints/stripe_balance_endpoints.py`, `stripe_meter_endpoints.py`
- **Railway config**: `Dockerfile.railway`, `railway.toml`, `proxy_server_config.railway.yaml`
- **Database tables**: `LiteLLM_StripeBalanceTable`, `LiteLLM_StripeTransactionTable`

## Key Patterns

### Provider Implementation
- Providers inherit from base classes in `litellm/llms/base.py`
- Each provider has transformation functions for input/output formatting
- Support both sync and async operations
- Handle streaming responses and function calling

### Error Handling
- Provider-specific exceptions mapped to OpenAI-compatible errors
- Fallback logic handled by Router system
- Comprehensive logging through `litellm/_logging.py`

### Configuration
- YAML config files for proxy server (see `proxy/example_config_yaml/`)
- Environment variables for API keys and settings
- Database schema managed via Prisma (`schema.prisma` in root)

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

## Development Notes

### Code Style
- Uses Black formatter, Ruff linter, MyPy type checker
- Pydantic v2 for data validation
- Async/await patterns throughout
- Type hints required for all public APIs

### Testing Strategy
- Unit tests in `tests/test_litellm/`
- Integration tests for each provider in `tests/llm_translation/`
- Proxy tests in `tests/proxy_unit_tests/`
- Load tests in `tests/load_tests/`

### Database Migrations
- Prisma handles schema migrations
- Migration files auto-generated with `prisma migrate dev`
- Stripe tables added: `LiteLLM_StripeBalanceTable`, `LiteLLM_StripeTransactionTable`

### Enterprise Features
- Enterprise-specific code in `enterprise/` directory
- Optional features enabled via environment variables

## Related Documentation

- `RAILWAY_DEPLOYMENT.md` - Railway deployment guide
- `STRIPE_PREPAID_SETUP.md` - Stripe billing setup
- `TAILSCALE_SUBNET_ROUTING.md` - VPN configuration
- `AGENTS.md` - Agent development instructions

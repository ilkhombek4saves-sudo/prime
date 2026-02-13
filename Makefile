# =============================================================================
#  MultiBot Aggregator — Developer Commands
#  Usage: make <target>
# =============================================================================

DOCKER_COMPOSE := docker compose
PYTHON         := python3
BACKEND        := backend

.DEFAULT_GOAL := help

# ── Colours ───────────────────────────────────────────────────────────────────
CYN := \033[96m
GRN := \033[92m
YLW := \033[93m
RED := \033[91m
WHT := \033[97m
DIM := \033[2m
RST := \033[0m
BLD := \033[1m

.PHONY: help onboard doctor \
        start stop restart build rebuild \
        logs logs-all status \
        shell db installer-up installer-down installer-public-up installer-public-down \
        test lint migrate install-cli \
        seed clean

# ── Help ──────────────────────────────────────────────────────────────────────
help: ## Show this help message
	@echo ""
	@echo "$(BLD)$(CYN) ███╗   ███╗██╗   ██╗██╗  ████████╗██╗██████╗  ██████╗ ████████╗$(RST)"
	@echo "$(BLD)$(CYN) ████╗ ████║██║   ██║██║  ╚══██╔══╝██║██╔══██╗██╔═══██╗╚══██╔══╝$(RST)"
	@echo "$(BLD)$(CYN) ██╔████╔██║██║   ██║██║     ██║   ██║██████╔╝██║   ██║   ██║   $(RST)"
	@echo "$(BLD)$(CYN) ██║╚██╔╝██║██║   ██║██║     ██║   ██║██╔══██╗██║   ██║   ██║   $(RST)"
	@echo "$(BLD)$(CYN) ██║ ╚═╝ ██║╚██████╔╝███████╗██║   ██║██████╔╝╚██████╔╝   ██║   $(RST)"
	@echo "$(BLD)$(CYN) ╚═╝     ╚═╝ ╚═════╝ ╚══════╝╚═╝   ╚═╝╚═════╝  ╚═════╝    ╚═╝   $(RST)"
	@echo ""
	@echo "$(DIM) MultiBot Aggregator — AI-powered Telegram bot platform$(RST)"
	@echo ""
	@echo "$(BLD)$(WHT)Setup$(RST)"
	@echo "  $(GRN)make onboard$(RST)      $(DIM)Interactive first-time setup wizard$(RST)"
	@echo "  $(GRN)make doctor$(RST)       $(DIM)Check system health and service status$(RST)"
	@echo ""
	@echo "$(BLD)$(WHT)Services$(RST)"
	@echo "  $(GRN)make start$(RST)        $(DIM)Start all services (detached)$(RST)"
	@echo "  $(GRN)make stop$(RST)         $(DIM)Stop all services$(RST)"
	@echo "  $(GRN)make restart$(RST)      $(DIM)Restart backend (picks up code changes)$(RST)"
	@echo "  $(GRN)make build$(RST)        $(DIM)Build Docker images$(RST)"
	@echo "  $(GRN)make rebuild$(RST)      $(DIM)Force-rebuild without cache$(RST)"
	@echo "  $(GRN)make status$(RST)       $(DIM)Show container status$(RST)"
	@echo ""
	@echo "$(BLD)$(WHT)Logs$(RST)"
	@echo "  $(GRN)make logs$(RST)         $(DIM)Follow backend logs$(RST)"
	@echo "  $(GRN)make logs-all$(RST)     $(DIM)Follow all service logs$(RST)"
	@echo ""
	@echo "$(BLD)$(WHT)Development$(RST)"
	@echo "  $(GRN)make shell$(RST)        $(DIM)Open bash shell in backend container$(RST)"
	@echo "  $(GRN)make db$(RST)           $(DIM)Open PostgreSQL interactive shell$(RST)"
	@echo "  $(GRN)make installer-up$(RST) $(DIM)Start temporary installer endpoint on :8081$(RST)"
	@echo "  $(GRN)make installer-down$(RST) $(DIM)Stop temporary installer endpoint$(RST)"
	@echo "  $(GRN)make installer-public-up$(RST) $(DIM)Start public HTTPS installer (80/443)$(RST)"
	@echo "  $(GRN)make installer-public-down$(RST) $(DIM)Stop public HTTPS installer$(RST)"
	@echo "  $(GRN)make test$(RST)         $(DIM)Run backend test suite$(RST)"
	@echo "  $(GRN)make lint$(RST)         $(DIM)Run ruff linter + black formatter check$(RST)"
	@echo "  $(GRN)make migrate$(RST)      $(DIM)Apply Alembic migrations in backend container$(RST)"
	@echo "  $(GRN)make install-cli$(RST)  $(DIM)Install 'prime' command into ~/.local/bin$(RST)"
	@echo "  $(GRN)make seed$(RST)         $(DIM)Seed demo data (dev only)$(RST)"
	@echo ""
	@echo "$(BLD)$(WHT)Danger zone$(RST)"
	@echo "  $(RED)make clean$(RST)        $(DIM)Stop services and wipe all data volumes$(RST)"
	@echo ""

# ── Setup ─────────────────────────────────────────────────────────────────────
onboard: ## Run the interactive setup wizard
	@$(PYTHON) scripts/onboard.py

doctor: ## Check system health
	@$(PYTHON) scripts/onboard.py --doctor

# ── Services ──────────────────────────────────────────────────────────────────
start: ## Start all services in background
	@echo "$(CYN)→$(RST) Starting MultiBot Aggregator..."
	@$(DOCKER_COMPOSE) up -d
	@echo "$(GRN)✓$(RST) Services started"
	@echo "  Admin UI:  $(WHT)http://localhost:5173$(RST)"
	@echo "  API:       $(WHT)http://localhost:8000$(RST)"
	@echo "  API docs:  $(WHT)http://localhost:8000/docs$(RST)"

stop: ## Stop all services
	@echo "$(YLW)→$(RST) Stopping services..."
	@$(DOCKER_COMPOSE) down
	@echo "$(GRN)✓$(RST) Services stopped"

restart: ## Restart backend service
	@echo "$(CYN)→$(RST) Restarting backend..."
	@$(DOCKER_COMPOSE) restart backend
	@echo "$(GRN)✓$(RST) Backend restarted"

build: ## Build Docker images
	@echo "$(CYN)→$(RST) Building images..."
	@$(DOCKER_COMPOSE) build

rebuild: ## Rebuild images without cache
	@echo "$(CYN)→$(RST) Rebuilding images (no cache)..."
	@$(DOCKER_COMPOSE) build --no-cache

status: ## Show service status
	@$(DOCKER_COMPOSE) ps

# ── Logs ──────────────────────────────────────────────────────────────────────
logs: ## Follow backend logs
	@$(DOCKER_COMPOSE) logs -f backend

logs-all: ## Follow all services logs
	@$(DOCKER_COMPOSE) logs -f

# ── Development ───────────────────────────────────────────────────────────────
shell: ## Open bash shell in backend container
	@$(DOCKER_COMPOSE) exec backend bash

db: ## Open PostgreSQL interactive shell
	@$(DOCKER_COMPOSE) exec db psql -U postgres multibot

installer-up: ## Start temporary installer endpoint
	@$(DOCKER_COMPOSE) up -d installer
	@echo "$(GRN)✓$(RST) Installer endpoint: $(WHT)http://localhost:8081/install.sh$(RST)"

installer-down: ## Stop temporary installer endpoint
	@$(DOCKER_COMPOSE) stop installer

installer-public-up: ## Start public HTTPS installer endpoint
	@$(DOCKER_COMPOSE) up -d installer-public
	@echo "$(GRN)✓$(RST) Public installer URL: $(WHT)https://wgrbojeweoginrb234.duckdns.org/install.sh$(RST)"

installer-public-down: ## Stop public HTTPS installer endpoint
	@$(DOCKER_COMPOSE) stop installer-public

test: ## Run backend tests
	@echo "$(CYN)→$(RST) Running tests..."
	@$(DOCKER_COMPOSE) exec backend pytest /app/tests -v

lint: ## Lint and format check
	@echo "$(CYN)→$(RST) Running ruff + black..."
	@$(DOCKER_COMPOSE) exec backend ruff check app/
	@$(DOCKER_COMPOSE) exec backend black --check app/

migrate: ## Apply Alembic migrations
	@echo "$(CYN)→$(RST) Applying migrations..."
	@$(DOCKER_COMPOSE) exec backend bash -lc "PYTHONPATH=/app alembic -c /app/alembic.ini upgrade head"

install-cli: ## Install prime command in ~/.local/bin
	@mkdir -p "$$HOME/.local/bin"
	@ln -sf "$(PWD)/prime" "$$HOME/.local/bin/prime"
	@echo "$(GRN)✓$(RST) Installed: $$HOME/.local/bin/prime"
	@echo "$(DIM)If needed, add this to your shell profile: export PATH=\"$$HOME/.local/bin:$$PATH\"$(RST)"

seed: ## Seed demo data
	@$(PYTHON) scripts/onboard.py --seed

# ── Danger zone ───────────────────────────────────────────────────────────────
clean: ## Stop and remove all data (DESTRUCTIVE)
	@echo ""
	@echo "$(RED)$(BLD)  ⚠  WARNING: This will permanently delete all data$(RST)"
	@echo "$(DIM)     Database, sessions, messages — everything will be lost$(RST)"
	@echo ""
	@echo "  Press $(BLD)Ctrl+C$(RST) to cancel, or wait 5 seconds to continue..."
	@sleep 5
	@$(DOCKER_COMPOSE) down -v
	@echo "$(GRN)✓$(RST) Cleaned"

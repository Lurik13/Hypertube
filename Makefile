COMPOSE := docker compose
VERSIONS := back/alembic/versions

.DEFAULT_GOAL := help
.PHONY: help up down restart build logs ps migrate migration psql seed test reset-db clean

help: ## List the available targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

.env:
	@echo "Missing .env: run 'cp .env.example .env' first." && exit 1

up: .env ## Build and start every service (migrations run automatically)
	$(COMPOSE) up -d --build --wait

down: ## Stop the services (data is kept)
	$(COMPOSE) down

restart: down up ## Restart every service

build: .env ## Rebuild the images
	$(COMPOSE) build

logs: ## Follow the logs (make logs s=api for one service)
	$(COMPOSE) logs -f $(s)

ps: ## Show the services' state
	$(COMPOSE) ps

migrate: ## Apply pending migrations now (also done when the api starts)
	$(COMPOSE) exec api alembic upgrade head

migration: ## Create the next numbered migration: make migration name=movies
	@test -n "$(name)" || (echo "Usage: make migration name=<what_it_does>" && exit 1)
	@rev=$$(printf '%04d' $$(( $$(ls $(VERSIONS)/[0-9]*.py | wc -l) + 1 ))); \
	file="$(VERSIONS)/$${rev}_$$(printf '%s' '$(name)' | tr 'A-Z' 'a-z' | tr -cs 'a-z0-9' '_').py"; \
	$(COMPOSE) run --rm --no-deps -T -e RUN_MIGRATIONS=0 api \
		python scripts/new_migration.py "$$rev" "$(name)" > "$$file" \
		&& echo "Created $$file" || { rm -f "$$file"; exit 1; }

psql: ## Open a SQL shell in the db container
	$(COMPOSE) exec db sh -c 'PGPASSWORD="$$APP_DB_PASSWORD" psql -U "$$APP_DB_USER" -d "$$POSTGRES_DB"'

seed: ## Insert fake data for local testing
	$(COMPOSE) exec api python -m app.seed

test: .env ## Run the backend test suite against the test database
	$(COMPOSE) --profile test run --rm --build api-test

reset-db: ## Delete ALL local data (database and media volumes)
	@printf "This deletes the local database and media. Continue? [y/N] " && read answer && [ "$$answer" = y ]
	$(COMPOSE) down -v

clean: ## Remove containers, volumes and locally built images
	$(COMPOSE) --profile test down -v --rmi local

# Keep every Compose operation scoped to this named POC project.
COMPOSE := docker compose -p hypertube-torrentmanagement -f compose.yaml

.PHONY: help build run start stop clean prune test cleanup-data

# Show the supported local lifecycle and data-management commands.
help:
	@printf '%s\n' \
		'build         Build the POC container' \
		'run           Build and run in the foreground' \
		'start         Build and run in the background' \
		'stop          Stop the POC containers' \
		'clean         Remove POC containers and networks; keep downloaded data' \
		'prune         Remove this POC containers, image, and persistent volumes' \
		'test          Run the focused unit tests in the container' \
		'cleanup-data  Stop the service and clear its downloaded files and records'

build:
	$(COMPOSE) build

# Run attached so startup and runtime messages remain visible to the operator.
run:
	$(COMPOSE) up --build

# Build and run the API with its health-checked PostgreSQL dependency.
start:
	$(COMPOSE) up --build -d

# Stop containers without removing either persistent volume.
stop:
	$(COMPOSE) stop

# Remove project containers and network while keeping downloaded and database data.
clean:
	$(COMPOSE) down --remove-orphans

# Destructive: remove only this project's containers, image, and named volumes.
prune:
	$(COMPOSE) down --remove-orphans --volumes --rmi local

# Run tests in a unique PostgreSQL schema after waiting for the database health check.
test: build
	$(COMPOSE) up -d --wait postgres
	$(COMPOSE) run --rm --no-deps torrentmanagement python -m unittest discover -s tests -v

# Clear media and PostgreSQL records through the operator-only cleanup utility.
cleanup-data:
	./scripts/cleanup.sh

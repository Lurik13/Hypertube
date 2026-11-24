COMPOSE := docker compose -p hypertube-torrentmanagement -f compose.yaml

.PHONY: help build run start stop clean prune test cleanup-data

help:
	@printf '%s\n' \
		'build         Build the POC container' \
		'run           Build and run in the foreground' \
		'start         Build and run in the background' \
		'stop          Stop the POC containers' \
		'clean         Remove POC containers and networks; keep downloaded data' \
		'prune         Remove this POC containers, image, and all its data volume' \
		'test          Run the focused unit tests in the container' \
		'cleanup-data  Stop the service and clear its downloaded files and records'

build:
	$(COMPOSE) build

run:
	$(COMPOSE) up --build

start:
	$(COMPOSE) up --build -d

stop:
	$(COMPOSE) stop

clean:
	$(COMPOSE) down --remove-orphans

prune:
	$(COMPOSE) down --remove-orphans --volumes --rmi local

test: build
	$(COMPOSE) run --rm --no-deps torrentmanagement python -m unittest discover -s tests -v

cleanup-data:
	./scripts/cleanup.sh

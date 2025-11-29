COMPOSE ?= docker compose

.PHONY: bootstrap dev refresh

bootstrap:
	$(COMPOSE) build
	$(COMPOSE) run --rm frontend npm install

dev:
	$(COMPOSE) up

refresh:
	$(COMPOSE) exec backend curl -X POST http://localhost:8000/refresh

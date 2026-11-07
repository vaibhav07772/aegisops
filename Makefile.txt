# AegisOps — convenience targets
.PHONY: help up down logs shell test clean rebuild

help:
	@echo "AegisOps Docker targets:"
	@echo "  make up        - Build + start API + UI"
	@echo "  make down      - Stop containers"
	@echo "  make logs      - Tail logs from all services"
	@echo "  make shell     - Open shell in API container"
	@echo "  make test      - Run pytest inside container"
	@echo "  make clean     - Stop + remove volumes + data"
	@echo "  make rebuild   - Force rebuild image"

up:
	docker-compose up --build -d
	@echo ""
	@echo "✅ AegisOps running:"
	@echo "   API: http://localhost:8000/docs"
	@echo "   UI:  http://localhost:8501"

down:
	docker-compose down

logs:
	docker-compose logs -f

shell:
	docker-compose exec api /bin/bash

test:
	docker-compose exec api pytest -v

clean:
	docker-compose down -v
	rm -rf data/chroma data/models data/*.db data/runs data/metrics data/logs data/traces

rebuild:
	docker-compose build --no-cache
	docker-compose up -d
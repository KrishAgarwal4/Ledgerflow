.PHONY: setup test dev-backend dev-frontend seed verify-ledger chaos-storm chaos-overdraft benchmark migrate cli-status cli-balance docker-up docker-down

setup:
	python3 -m venv backend/venv
	backend/venv/bin/pip install --upgrade pip
	backend/venv/bin/pip install -r backend/requirements.txt
	npm --prefix frontend install

test:
	PYTHONPATH=. backend/venv/bin/pytest backend/tests -v

migrate:
	PYTHONPATH=. backend/venv/bin/alembic -c backend/alembic.ini upgrade head

seed:
	PYTHONPATH=. backend/venv/bin/python -m backend.app.seed.seed_data

benchmark:
	PYTHONPATH=. backend/venv/bin/python scripts/benchmark.py

cli-status:
	PYTHONPATH=. backend/venv/bin/python -m backend.cli status

cli-balance:
	PYTHONPATH=. backend/venv/bin/python -m backend.cli ledger balance

dev-backend:
	PYTHONPATH=. backend/venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

dev-frontend:
	npm --prefix frontend run dev -- --host 0.0.0.0 --port 5173

verify-ledger:
	curl -s http://localhost:8000/v1/ledger/verify | python3 -m json.tool

chaos-storm:
	curl -s -X POST http://localhost:8000/v1/chaos/meter-storm \
		-H "Content-Type: application/json" \
		-d '{"concurrency_count": 100, "customer_id": "cus_nexus_ai", "metric_name": "llm_tokens", "quantity": 50000}' | python3 -m json.tool

chaos-overdraft:
	curl -s -X POST http://localhost:8000/v1/chaos/overdraft-race \
		-H "Content-Type: application/json" \
		-d '{"concurrency_count": 20, "customer_id": "cus_quantum_labs", "charge_amount_cents": 1000, "initial_wallet_balance_cents": 5000}' | python3 -m json.tool

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down -v

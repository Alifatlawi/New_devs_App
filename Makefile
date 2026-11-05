back:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

front:
	cd frontend && npm run dev

pre-commit:
	cd backend && uv add --dev pre-commit
	uv run pre-commit install --install-hooks --overwrite

uv-install:
	cd backend && uv sync

# Backend tests, run inside the running backend container (docker compose up first)
test:
	docker compose exec backend sh -c "pip install -q -r requirements-dev.txt && python -m pytest -q"

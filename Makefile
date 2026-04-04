.PHONY: install run dev serve desktop clean

# One command to rule them all
install:
	@echo "Installing Planex..."
	@command -v uv >/dev/null || (echo "Installing uv..." && curl -LsSf https://astral.sh/uv/install.sh | sh)
	uv venv --python 3.11 .venv 2>/dev/null || true
	. .venv/bin/activate && uv pip install -e ".[dashboard,desktop]"
	cd frontend && npm install
	@echo ""
	@echo "✓ Planex installed. Run: make run"

# Desktop app (recommended)
run:
	. .venv/bin/activate && python desktop.py

# Web app (backend + frontend dev server)
dev:
	@echo "Starting backend on :8000 and frontend on :3000..."
	. .venv/bin/activate && planex serve & cd frontend && npm run dev

# Backend only
serve:
	. .venv/bin/activate && planex serve

# Build frontend for production/desktop
build:
	cd frontend && npm run build

# CLI one-shot
research:
	@read -p "Research goal: " goal && . .venv/bin/activate && planex run "$$goal" -y

clean:
	rm -rf .venv frontend/node_modules frontend/dist __pycache__ *.egg-info

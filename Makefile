.PHONY: help install run dev serve build research app stop clean desktop

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install Python + frontend dependencies
	@echo "Installing Planex..."
	@command -v uv >/dev/null || (echo "Installing uv..." && curl -LsSf https://astral.sh/uv/install.sh | sh)
	uv venv --python 3.11 .venv 2>/dev/null || true
	. .venv/bin/activate && uv pip install -e ".[dashboard,desktop,bedrock]"
	cd frontend && npm install
	@echo ""
	@echo "✓ Planex installed. Run: make run"

run: ## Start Planex (auto-detects SageMaker vs desktop)
	@if [ -n "$$SAGEMAKER_APP_TYPE" ]; then \
		echo "SageMaker Studio detected ($$SAGEMAKER_APP_TYPE) — building frontend + starting server..."; \
		cd frontend && npm run build && cd .. && \
		echo "" && \
		echo "✓ Open Planex via SageMaker proxy:" && \
		echo "  Click: https://<your-studio-domain>/jupyter/default/proxy/8000/" && \
		echo "" && \
		. .venv/bin/activate && planex serve; \
	else \
		. .venv/bin/activate && python desktop.py; \
	fi

desktop: ## Launch native desktop app (local only)
	. .venv/bin/activate && python desktop.py

dev: ## Start backend + frontend dev servers
	@echo "Starting backend on :8000 and frontend on :3000..."
	. .venv/bin/activate && planex serve & cd frontend && npm run dev

serve: ## Start backend API server only
	. .venv/bin/activate && planex serve

build: ## Build frontend for production
	cd frontend && npm run build

research: ## Run a one-shot research query via CLI
	@read -p "Research goal: " goal && . .venv/bin/activate && planex run "$$goal" -y

app: build ## Build macOS .app bundle
	@mkdir -p Planex.app/Contents/{MacOS,Resources}
	@printf '#!/bin/bash\nDIR="$$(cd "$$(dirname "$$0")/../../.." && pwd)"\ncd "$$DIR"\nsource .venv/bin/activate 2>/dev/null || true\nexec python3 desktop.py\n' > Planex.app/Contents/MacOS/Planex
	@chmod +x Planex.app/Contents/MacOS/Planex
	@printf '<?xml version="1.0"?>\n<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n<plist version="1.0"><dict><key>CFBundleName</key><string>Planex</string><key>CFBundleExecutable</key><string>Planex</string><key>CFBundleIconFile</key><string>icon</string><key>CFBundleIdentifier</key><string>com.planex.app</string><key>NSHighResolutionCapable</key><true/></dict></plist>' > Planex.app/Contents/Info.plist
	@mkdir -p /tmp/planex.iconset && sips -z 512 512 assets/icon.png --out /tmp/planex.iconset/icon_512x512.png >/dev/null 2>&1 && sips -z 256 256 assets/icon.png --out /tmp/planex.iconset/icon_256x256.png >/dev/null 2>&1 && iconutil -c icns /tmp/planex.iconset -o Planex.app/Contents/Resources/icon.icns 2>/dev/null || true
	@echo "✓ Planex.app created. Double-click to launch."

stop: ## Stop running Planex server
	@pkill -f "planex serve" 2>/dev/null && echo "Planex stopped." || echo "No running Planex server found."
	@pkill -f "uvicorn.*8000" 2>/dev/null || true

clean: ## Remove venv, node_modules, dist, caches
	rm -rf .venv frontend/node_modules frontend/dist __pycache__ *.egg-info Planex.app

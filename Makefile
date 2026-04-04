.PHONY: install run dev serve app clean

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

# Build macOS .app bundle
app: build
	@mkdir -p Planex.app/Contents/{MacOS,Resources}
	@printf '#!/bin/bash\nDIR="$$(cd "$$(dirname "$$0")/../../.." && pwd)"\ncd "$$DIR"\nsource .venv/bin/activate 2>/dev/null || true\nexec python3 desktop.py\n' > Planex.app/Contents/MacOS/Planex
	@chmod +x Planex.app/Contents/MacOS/Planex
	@printf '<?xml version="1.0"?>\n<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n<plist version="1.0"><dict><key>CFBundleName</key><string>Planex</string><key>CFBundleExecutable</key><string>Planex</string><key>CFBundleIconFile</key><string>icon</string><key>CFBundleIdentifier</key><string>com.planex.app</string><key>NSHighResolutionCapable</key><true/></dict></plist>' > Planex.app/Contents/Info.plist
	@mkdir -p /tmp/planex.iconset && sips -z 512 512 assets/icon.png --out /tmp/planex.iconset/icon_512x512.png >/dev/null 2>&1 && sips -z 256 256 assets/icon.png --out /tmp/planex.iconset/icon_256x256.png >/dev/null 2>&1 && iconutil -c icns /tmp/planex.iconset -o Planex.app/Contents/Resources/icon.icns 2>/dev/null || true
	@echo "✓ Planex.app created. Double-click to launch."

clean:
	rm -rf .venv frontend/node_modules frontend/dist __pycache__ *.egg-info Planex.app

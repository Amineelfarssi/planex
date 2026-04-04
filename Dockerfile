FROM python:3.11-slim AS backend

WORKDIR /app
RUN pip install uv

COPY pyproject.toml ./
COPY core/ core/
COPY tools/ tools/
COPY cli/ cli/
COPY dashboard/ dashboard/
COPY main.py desktop.py ./
COPY assets/ assets/
COPY examples/ examples/

RUN uv pip install --system -e ".[dashboard]"

# Build frontend
FROM node:18-slim AS frontend

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Final image
FROM python:3.11-slim

WORKDIR /app
RUN pip install uv

COPY --from=backend /app /app
COPY --from=frontend /app/frontend/dist /app/frontend/dist

RUN uv pip install --system -e ".[dashboard]"

EXPOSE 8000

CMD ["uvicorn", "dashboard.app:app", "--host", "0.0.0.0", "--port", "8000"]

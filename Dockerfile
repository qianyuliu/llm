# ---- Stage 1: install dependencies ----
FROM python:3.12-slim AS builder

WORKDIR /build

# Copy only what pip needs so the layer is cached when source changes
COPY pyproject.toml README.md ./
# Minimal source so `pip install .` can resolve the package
COPY app/__init__.py app/__init__.py
COPY custom_resolvers.py ./

RUN pip install --no-cache-dir .

# ---- Stage 2: runtime image ----
FROM python:3.12-slim

WORKDIR /app

# Bring installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages \
                    /usr/local/lib/python3.12/site-packages

# Copy application source
COPY app/ app/
COPY custom_resolvers.py ./
COPY config/ config/

# Container must listen on all interfaces
ENV HOST=0.0.0.0
ENV PORT=18080
ENV PYTHONUNBUFFERED=1

EXPOSE 18080

CMD ["python", "-m", "app.main"]

FROM ghcr.io/astral-sh/uv:python3.10-bookworm-slim
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=0

# Expose the required port
EXPOSE 6969

# Set up working directory
WORKDIR /app

# Install system dependencies, clean up cache to keep image size small
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    cmake \
    tk \
    ffmpeg \
    tini \
    && apt clean && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

# 의존성만 우선 설치
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY . .

# 앱 설치
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Define volumes for persistent storage
VOLUME ["/app/logs/"]

# Set environment variables if necessary
ENV PATH="/app/.venv/bin:$PATH"

# Run the app
ENTRYPOINT ["python3"]
CMD ["app.py"]

COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["tini", "-g", "--", "/app/entrypoint.sh"]
CMD []
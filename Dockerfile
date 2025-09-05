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
    && apt clean && rm -rf /var/lib/apt/lists/*

COPY . .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev   # deps만

# 프로젝트 설치
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev                        # 앱 설치

# Define volumes for persistent storage
VOLUME ["/app/logs/"]

# Set environment variables if necessary
ENV PATH="/app/.venv/bin:$PATH"

# Run the app
ENTRYPOINT ["python3"]
CMD ["app.py"]

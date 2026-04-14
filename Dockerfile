FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    portaudio19-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY . .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS runtime
ENV UV_PYTHON_DOWNLOADS=0
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    tk \
    tini \
    git \
    libportaudio2 \
    libatomic1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app /app

# 의존성만 builder에서 복사: 자주 안 바뀜
COPY --from=builder /app/.venv /app/.venv

# 소스는 컨텍스트에서 복사: 자주 바뀌지만 작게 만들 수 있음
COPY . /app

EXPOSE 6969 7001 7002 7003 7004 7005 7006 7007 7008 7009 7010
VOLUME ["/app/logs/"]
ENV PATH="/app/.venv/bin:$PATH"

RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["tini", "-g", "--", "/app/entrypoint.sh"]
CMD []
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

# 의존성 파일만 먼저 복사 → 소스 변경 시 캐시 재사용
COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# 소스는 의존성 설치 이후에 복사
COPY . .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ── runtime ────────────────────────────────────────────────
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
    # build-essential 제거 — 런타임에 컴파일 불필요

# .venv만 builder에서 가져오기 (소스는 호스트에서 직접)
COPY --from=builder /app/.venv /app/.venv

# 소스는 호스트에서 복사
COPY . /app

EXPOSE 6969 7001 7002 7003 7004 7005 7006 7007 7008 7009 7010
VOLUME ["/app/logs/"]
ENV PATH="/app/.venv/bin:$PATH"

RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["tini", "-g", "--", "/app/entrypoint.sh"]
CMD []
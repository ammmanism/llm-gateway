FROM python:3.11-slim-bookworm AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends gcc libffi-dev && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir hatch && hatch dep show requirements > requirements.txt && pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels -r requirements.txt

FROM python:3.11-slim-bookworm AS production
WORKDIR /app
RUN groupadd -r omnimodal && useradd -r -g omnimodal omnimodal
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/* && apt-get clean
COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels
COPY src/omnimodal/ ./omnimodal/
COPY README.md .
RUN chown -R omnimodal:omnimodal /app
USER omnimodal
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 OMNI_ENV=production
CMD ["uvicorn", "omnimodal.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

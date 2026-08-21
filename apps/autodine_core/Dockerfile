FROM python:3.12-slim

WORKDIR /workspace
COPY pyproject.toml README.md ./
COPY apps/autodine_core ./apps/autodine_core
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

COPY data ./data
COPY scripts ./scripts
COPY deploy ./deploy
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "autodine_core.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

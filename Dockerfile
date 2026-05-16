FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY pyproject.toml README.md ./
COPY homeassistant_proxy ./homeassistant_proxy

RUN pip install --no-cache-dir .

RUN mkdir -p /app/data/backups && chown -R app:app /app/data

USER app

EXPOSE 8000

CMD ["uvicorn", "homeassistant_proxy.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

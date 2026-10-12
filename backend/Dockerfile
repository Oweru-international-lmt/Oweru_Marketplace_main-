FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DJANGO_SETTINGS_MODULE=config.settings.production
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgdal32 libgeos-c1v5 libpq5 && rm -rf /var/lib/apt/lists/*
COPY requirements-production.txt ./
RUN pip install --no-cache-dir -r requirements-production.txt && pip check
RUN groupadd --gid 10001 marketplace && useradd --uid 10001 --gid marketplace --no-create-home marketplace
COPY --chown=marketplace:marketplace . .
RUN mkdir -p /app/staticfiles && chown marketplace:marketplace /app/staticfiles
USER 10001:10001
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--config", "gunicorn.conf.py"]

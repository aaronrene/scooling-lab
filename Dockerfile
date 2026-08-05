# Scooling Lab — minimal always-on API for Railway / container hosts.
FROM python:3.12-slim

WORKDIR /app

# Install package (stdlib + setuptools layout under src/).
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY src ./src
RUN pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1
ENV SCOOLING_LAB_HOST=0.0.0.0
ENV PORT=8080
EXPOSE 8080

# Railway injects PORT; api.main() honors it.
CMD ["python", "-m", "scooling_lab.api"]

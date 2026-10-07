FROM python:3.12-slim

# PYTHONUNBUFFERED makes print/log output show up immediately in `docker compose logs`.
# PYTHONDONTWRITEBYTECODE stops Python writing .pyc files inside the container.
# DB_PATH puts the database on the /data volume (see docker-compose.yml).
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DB_PATH=/data/challenge.db

WORKDIR /app

# Install dependencies first. Docker caches this layer, so rebuilds are fast
# unless requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the bot's code (see .dockerignore for what is left out, like .env)
COPY . .

# Run as a normal user instead of root, and create /data owned by that user
RUN useradd --create-home botuser \
    && mkdir /data \
    && chown botuser:botuser /data
USER botuser

CMD ["python", "bot.py"]

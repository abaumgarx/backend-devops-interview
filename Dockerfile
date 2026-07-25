FROM python:3.13-slim-trixie

RUN apt update && apt install -y curl libpq-dev gcc
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/

WORKDIR /app
COPY . .
RUN uv sync

ENTRYPOINT ["sh", "-c", "uv run python manage.py migrate && uv run python manage.py seed && uv run python manage.py runserver 0.0.0.0:8000"]

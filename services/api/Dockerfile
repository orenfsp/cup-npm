FROM python:3.12.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system --gid 10001 otklik \
    && adduser --system --uid 10001 --ingroup otklik --no-create-home otklik \
    && mkdir -p /var/lib/otklik/attachments \
    && chown -R otklik:otklik /var/lib/otklik

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY --chown=otklik:otklik pyproject.toml alembic.ini ./
COPY --chown=otklik:otklik app ./app
COPY --chown=otklik:otklik alembic ./alembic

USER otklik
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

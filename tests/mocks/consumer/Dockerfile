# syntax=docker/dockerfile:1.2
FROM python:3.9-slim

SHELL ["/bin/bash", "-c"]

RUN apt-get update && apt-get -y upgrade \
    && apt-get -y install --no-install-recommends \
        curl python3-dev gcc \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get -y clean

# Security: Do NOT supply these except in local builds (that are not
# pushed) or docker-compose/skaffold/etc testing. CI should use buildkit
# and pass a secret file instead, handled by `set-build-secrets.sh`
# We include this for compatibility with docker-compose, because 
# compose does not (seem to) have a secret path into builds, just runs. 
# So: 
# 
#   CI can use --secret, and obscure credentials
#   compose can use these ARGs, and reveal credentials (locally only)
#   set-build-secrets.sh can "join" the two paths in either context
# 
# See also https://github.com/docker/compose/pull/7046
# 
ARG ARTIFACTORY_USER
ARG ARTIFACTORY_API_KEY

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_HOME="/etc/poetry" \
    POETRY_NO_INTERACTION=1 \
    POETRY_VERSION=1.1.13

ENV POETRY_PATH="${POETRY_HOME}/bin/poetry"

WORKDIR /app

# https://python-poetry.org/docs/master/#installation
RUN curl -sSL https://install.python-poetry.org | python3 -
RUN cd /usr/local/bin && ln -s ${POETRY_PATH} && chmod +x ${POETRY_PATH}

COPY ./tests/mocks/consumer/poetry.lock ./tests/mocks/consumer/pyproject.toml ./
RUN poetry config virtualenvs.create false \
    && poetry install -vvv --no-dev

COPY ./tests/mocks/consumer/app ./app/
COPY ./generated/python/standardproto/ ./
COPY ./schemas ./schemas/

CMD ["python","-m","app"]

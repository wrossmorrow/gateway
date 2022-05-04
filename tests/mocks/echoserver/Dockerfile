FROM python:3.9-slim

RUN apt-get update && apt-get upgrade -y \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get -y clean

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY tests/mocks/echoserver/app ./app

CMD ["python","-m","app"]

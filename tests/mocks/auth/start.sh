#!/bin/bash
uvicorn --host 0.0.0.0 --port ${APP_PORT} --workers 2 app:app
from os import environ

PORT = int(environ.get("ECHO_PORT", "8000"))

ECHO_MESSAGE = environ.get("ECHO_MESSAGE", "Hello")

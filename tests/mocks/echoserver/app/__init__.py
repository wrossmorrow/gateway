import http.server
import json
from urllib.parse import parse_qs

from .settings import ECHO_MESSAGE

Handler = http.server.BaseHTTPRequestHandler


class EchoHandler(Handler):
    protocol_version = "HTTP/1.0"
    rsp = {"command": None, "path": None, "message": ECHO_MESSAGE}

    def write_response(self):
        self.rsp["command"] = self.command
        if self.path.startswith("/redirect"):
            self.send_response(308)
            _, _, queries = self.path.partition("?")
            params = parse_qs(queries)
            self.send_header("location", params["location"][0])
        else:
            self.send_response(200)
        self.rsp["path"] = self.path
        b = json.dumps(self.rsp).encode("UTF-8")
        self.send_header("Request-Handler-Was", str(self.headers.get("Host")))
        for key, value in self.headers.items():
            self.send_header(f"X-Echo-{key}", value)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(b)

    def do_GET(self):
        self.write_response()

    def do_POST(self):
        self.write_response()

    def do_PUT(self):
        self.write_response()

    def do_PATH(self):
        self.write_response()

    def do_DELETE(self):
        self.write_response()

    def do_OPTION(self):
        self.write_response()

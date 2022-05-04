from socketserver import TCPServer

from . import EchoHandler
from .settings import PORT

with TCPServer(("", PORT), EchoHandler) as httpd:
    print("serving at port", PORT)
    httpd.serve_forever()

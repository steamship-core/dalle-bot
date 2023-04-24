"""Utils for local testing."""
import json
import logging
from http import server
from socketserver import TCPServer
from typing import Optional

from http_handler import create_safe_handler
from pyngrok import ngrok
from steamship import Steamship
from steamship.invocable import (
    Invocable,
    InvocableRequest,
    Invocation,
    InvocationContext,
    LoggingConfig,
)


def make_handler(
    invocable: Invocable, client: Steamship, context: InvocationContext, config: dict = {}
):
    """Create a handler for HTTP traffic."""

    class LocalHttpHandler(server.SimpleHTTPRequestHandler):
        def _set_response(self):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

        def do_GET(self):
            logging.info(
                "GET request,\nPath: %s\nHeaders:\n%s\n", str(self.path), str(self.headers)
            )
            self._set_response()
            self.wfile.write("GET request for {}".format(self.path).encode("utf-8"))

        def do_POST(self):
            content_length = int(self.headers["Content-Length"])  # <--- Gets the size of data
            post_data = self.rfile.read(content_length)  # <--- Gets the data itself
            try:
                data_str = post_data.decode("utf8")
                post_json = json.loads(data_str)

                invocation = Invocation(
                    http_verb="POST", invocation_path=self.path, arguments=post_json, config=config
                )
                event = InvocableRequest(
                    client_config=client.config,
                    invocation=invocation,
                    logging_config=LoggingConfig(logging_host=None, logging_port=None),
                    invocation_context=context,
                )

                handler = create_safe_handler(invocable)
                handler(event.dict(by_alias=True), context)

                InvocableRequest.parse_obj(event.dict())

                logging.info(
                    "POST request,\nPath: %s\nHeaders:\n%s\n\nBody:\n%s\n",
                    str(self.path),
                    str(self.headers),
                    post_data.decode("utf-8"),
                )
                self._set_response()
                self.wfile.write("POST request for {}".format(self.path).encode("utf-8"))
            except Exception as e:
                print(e)
                self._set_response()
                self.wfile.write("POST request for {}".format(self.path).encode("utf-8"))

    return LocalHttpHandler


def use_local_with_ngrok(
    client: Steamship, package_class, config: Optional[dict] = None, port: int = 8080
):
    """Configure a local-host compatible instance and wires an HTTP endpoint up to it."""
    # Open an HTTP tunnel on the default port 80
    # <NgrokTunnel: "http://<public_sub>.ngrok.io" -> "http://localhost:80">
    http_tunnel = ngrok.connect(port, bind_tls=True)

    public_url = http_tunnel.public_url
    print("🚢 Development Hosting 🚢")
    print(f"URL: {public_url}")
    print("Client Auth: Hardcoded")

    # We need to trigger the instance init.
    context = InvocationContext(invocable_url=f"{public_url}/")

    # Now start the server
    httpd = TCPServer(("", port), make_handler(package_class, client, context, config))

    invocation = Invocation(
        http_verb="POST", invocation_path="__dir__", arguments={}, config=config
    )
    event = InvocableRequest(
        client_config=client.config,
        invocation=invocation,
        logging_config=LoggingConfig(logging_host=None, logging_port=None),
        invocation_context=context,
    )
    handler = create_safe_handler(package_class)
    handler(event.dict(by_alias=True), context)

    print("Now serving...")
    httpd.serve_forever()

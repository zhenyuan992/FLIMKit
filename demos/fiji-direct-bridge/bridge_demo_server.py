import json
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO

import numpy as np
import tifffile


@dataclass
class BridgeState:
    intensity: np.ndarray
    lifetime: np.ndarray
    received_rois: list[dict] = field(default_factory=list)


def create_server(host: str, port: int, token: str, state: BridgeState):
    class Handler(BaseHTTPRequestHandler):
        def _authorized(self):
            return self.headers.get('Authorization') == f'Bearer {token}'

        def do_GET(self):
            if self.path == '/v1/status':
                body = json.dumps({
                    'protocol': 'flimkit-fiji',
                    'protocol_version': 1,
                }).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path in ('/v1/images/intensity.tif', '/v1/images/lifetime.tif'):
                if not self._authorized():
                    self.send_error(401)
                    return
                image_id = self.path.rsplit('/', 1)[-1].removesuffix('.tif')
                buffer = BytesIO()
                tifffile.imwrite(buffer, getattr(state, image_id).astype(np.float32))
                body = buffer.getvalue()
                self.send_response(200)
                self.send_header('Content-Type', 'image/tiff')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404)

        def do_POST(self):
            if self.path != '/v1/rois':
                self.send_error(404)
                return
            if not self._authorized():
                self.send_error(401)
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                payload = json.loads(self.rfile.read(length).decode('utf-8'))
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                self.send_error(400)
                return
            if payload.get('type') != 'FeatureCollection':
                self.send_error(400)
                return
            state.received_rois.append(payload)
            body = json.dumps({
                'received_features': len(payload.get('features', [])),
            }).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer((host, port), Handler)
    server.token = token
    server.state = state
    return server

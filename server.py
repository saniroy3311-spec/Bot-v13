import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, data: object, status: int = 200) -> None:
        try:
            body = json.dumps(data).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            pass

    def do_GET(self):
        if self.path == '/api/status':
            self._send_json({'status': 'online', 'symbol': 'BTC/USD:USD', 'timeframe': '3m'})
        else:
            self._send_json({'message': 'Bot v13 Live Dashboard Active'})

def run_server(host='0.0.0.0', port=10000):
    try:
        server = HTTPServer((host, port), DashboardHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        print(f'[SERVER] Dashboard LIVE -> http://{host}:{port}')
        return server
    except Exception as e:
        print(f'[SERVER] Note on port {port}: {e}')
        return None

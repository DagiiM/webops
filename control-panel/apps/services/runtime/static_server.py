"""Serve only published assets with bounded concurrency and no directory indexes."""
import os
import mimetypes
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

class Handler(SimpleHTTPRequestHandler):
    def list_directory(self,path):
        self.send_error(404)
        return None
    def setup(self):
        self.request.settimeout(5)
        super().setup()
    def end_headers(self):
        self.send_header("X-Content-Type-Options","nosniff")
        super().end_headers()

class Server(ThreadingHTTPServer):
    slots=threading.BoundedSemaphore(8)
    daemon_threads=True
    def process_request(self,request,address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:super().process_request(request,address)
        except BaseException:
            self.slots.release()
            raise
    def process_request_thread(self,request,address):
        try:super().process_request_thread(request,address)
        finally:self.slots.release()

if __name__=="__main__":
    mimetypes.knownfiles = []
    mimetypes.init(files=[])
    Server(("127.0.0.1",int(os.environ["PORT"])),Handler).serve_forever()

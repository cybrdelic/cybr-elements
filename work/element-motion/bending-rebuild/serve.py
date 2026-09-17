"""Local threaded preview with byte-range support for independent video seeking."""
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
import os,re
ROOT=Path(__file__).resolve().parents[3]/'outputs/cybrdelic-type'
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT),**kwargs)
    def send_head(self):
        self.byte_range=None
        path=Path(self.translate_path(self.path))
        header=self.headers.get('Range')
        if header and path.is_file():
            match=re.fullmatch(r'bytes=(\d*)-(\d*)',header)
            size=path.stat().st_size
            if match:
                first,last=match.groups()
                start=int(first) if first else max(0,size-int(last))
                end=min(size-1,int(last)) if first and last else size-1
                if start>=size or start>end:
                    self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.end_headers();return None
                stream=path.open('rb');stream.seek(start);self.byte_range=(start,end)
                self.send_response(206);self.send_header('Content-Type',self.guess_type(str(path)));self.send_header('Accept-Ranges','bytes');self.send_header('Content-Range',f'bytes {start}-{end}/{size}');self.send_header('Content-Length',str(end-start+1));self.end_headers();return stream
        return super().send_head()
    def copyfile(self,source,target):
        if self.byte_range:
            remaining=self.byte_range[1]-self.byte_range[0]+1
            while remaining:
                chunk=source.read(min(256*1024,remaining))
                if not chunk:break
                target.write(chunk);remaining-=len(chunk)
        else:super().copyfile(source,target)
    def log_message(self,fmt,*args):
        if args and str(args[1] if len(args)>1 else '') not in ['200','206','304']:
            super().log_message(fmt,*args)
ThreadingHTTPServer(('127.0.0.1',8767),Handler).serve_forever()

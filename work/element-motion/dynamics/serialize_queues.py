"""Let the current frame job finish, then serialize our two owned queues."""
import sys,psutil
a,b=map(int,sys.argv[1:])
first=psutil.Process(a);second=psutil.Process(b)
for p in (first,second):
    assert any(x.replace('\\','/').endswith('/dynamics/render_all.py') for x in p.cmdline()),'Unowned queue'
second.suspend()
print('Second queue paused between jobs; its current Blender child can finish.',flush=True)
try:
    first.wait()
finally:
    if second.is_running():second.resume()
print('Second queue resumed.',flush=True)

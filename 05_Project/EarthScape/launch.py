"""Desktop launcher: starts the local application and opens the browser."""
import os,sys,time,subprocess,webbrowser,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parent;os.chdir(root)
os.environ.setdefault('EARTHSCAPE_ADMIN_PASSWORD','EarthDemo!2026');os.environ.setdefault('EARTHSCAPE_ANALYST_PASSWORD','AnalystDemo!2026');os.environ.setdefault('EARTHSCAPE_VIEWER_PASSWORD','ViewerDemo!2026')
try:
 r=urllib.request.urlopen('http://127.0.0.1:8080/api/me',timeout=1)
except urllib.error.HTTPError as e:
 if e.code==401:webbrowser.open('http://127.0.0.1:8080');raise SystemExit(0)
except (OSError,urllib.error.URLError):pass
log=(root/'runtime/launcher.log');log.parent.mkdir(exist_ok=True)
with log.open('a') as out:
 process=subprocess.Popen([sys.executable,str(root/'app.py')],stdout=out,stderr=out)
 for i in range(100):
  if process.poll() is not None:print('Application startup failed. Read runtime/launcher.log');raise SystemExit(1)
  try:
   urllib.request.urlopen('http://127.0.0.1:8080',timeout=1);webbrowser.open('http://127.0.0.1:8080');break
  except (OSError,urllib.error.URLError):time.sleep(.2)
 else:process.terminate();raise SystemExit('Startup timeout. Read runtime/launcher.log')
 print('EarthScape is running. Keep this window open. Press Ctrl+C to stop.\nAdmin: admin / EarthDemo!2026')
 try:process.wait()
 except KeyboardInterrupt:process.terminate();process.wait()

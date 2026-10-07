@echo off
setlocal
cd /d "%~dp0..\.."
set "SITE_ROOT=%CD%\outputs\cybrdelic-type"
set "STUDIO_URL=http://127.0.0.1:8767/elements/motion/bending/sigils/02/fire-live/?simulation=original&preset=hearth&fuel=gas&room=1&lighting=fully-lit"

rem Reuse the server if this project is already being served.
curl --silent --fail --output NUL "%STUDIO_URL%" >NUL 2>&1
if errorlevel 1 (
  where py >NUL 2>&1
  if errorlevel 1 (
    echo Python 3 was not found. Install Python or open the hosted demo:
    echo https://cybrdelic.github.io/firesim/
    pause
    exit /b 1
  )
  start "Fire Studio local server" /min py -3 -m http.server 8767 --bind 127.0.0.1 --directory "%SITE_ROOT%"
  set /a ATTEMPTS=0
  :wait_for_server
  curl --silent --fail --output NUL "%STUDIO_URL%" >NUL 2>&1
  if not errorlevel 1 goto open_studio
  set /a ATTEMPTS+=1
  if %ATTEMPTS% GEQ 20 (
    echo Fire Studio local server did not start. Check that port 8767 is available.
    pause
    exit /b 1
  )
  timeout /t 1 /nobreak >NUL
  goto wait_for_server
)

:open_studio
start "" "%STUDIO_URL%"
endlocal

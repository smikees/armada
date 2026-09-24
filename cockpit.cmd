@echo off
REM Double-click to launch the live ARMADA cockpit, then open the browser.
REM Leave this window open while you use the cockpit; close it (or Ctrl-C) to stop.
REM No realm is named: it serves the last one you had open. Pass a folder to force one:
REM   cockpit.cmd "D:\Work\Hand-realm"
cd /d "%~dp0"
start "" http://127.0.0.1:8756
where python >nul 2>nul
if %errorlevel%==0 ( python -m armada serve %* --port 8756 ) else ( py -m armada serve %* --port 8756 )

@echo off
REM ARMADA launcher — auto-cd to the app folder so `python -m armada` resolves,
REM then forward all args to the CLI. Usage examples:
REM   armada.cmd doctor --realm "D:\Work\Hand" --engine claude
REM   armada.cmd run examples\demo-realm scout hello --engine claude
REM   armada.cmd open "D:\Work\Hand"
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 ( python -m armada %* ) else ( py -m armada %* )

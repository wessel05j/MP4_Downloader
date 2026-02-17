@echo off
cd /d "%~dp0"
call run.bat %*
exit /b %ERRORLEVEL%

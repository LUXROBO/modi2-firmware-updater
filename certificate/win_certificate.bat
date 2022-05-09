@echo off

set SCRIPT_PATH=%~dp0
set ROOT_PATH=%SCRIPT_PATH%
set APP_PATH=%ROOT_PATH%\..\dist
if not exist %APP_PATH% (
    echo dist directory does not exist.
)

set SIGN_TOOL_PATH="C:\Program Files (x86)\Windows Kits\10\bin\10.0.22000.0\x64"
if not exist %SIGN_TOOL_PATH% (
    echo sign tool directory does not exist.
)

set TOKEN=%1
set CONT=%2
set APP_NAME=%~3

echo %APP_NAME%

cd %SIGN_TOOL_PATH%
.\signtool.exe sign /f .\luxrobo.cer /csp "eToken Base Cryptographic Provider" /k "[{{%TOKEN%}}]=%CONT%" /fd sha1 /tr http://timestamp.digicert.com /td sha1 "%APP_PATH%\%APP_NAME%""
cd %ROOT_PATH%
@echo off
setlocal
cd /d "%~dp0"
docker info >nul 2>&1
if errorlevel 1 (
 echo Install and start Docker Desktop, then double-click this file again.
 echo The offline application can be opened now using START_EARTHSCAPE.bat.
 pause
 exit /b 1
)
docker compose up --build -d
if errorlevel 1 (
 pause
 exit /b 1
)
powershell -NoProfile -Command "$ready=$false; for($i=0;$i -lt 180;$i++){try{Invoke-WebRequest http://localhost:8081 -UseBasicParsing -TimeoutSec 2 | Out-Null; $ready=$true; break}catch{Start-Sleep -Seconds 2}}; if($ready){Start-Process http://localhost:8081}else{Write-Host 'Stack is still initializing; check docker compose logs.'}"
echo EarthScape Hadoop stack: http://localhost:8081
pause

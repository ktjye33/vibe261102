# 코스피200 크롤러를 Windows 실행파일(.exe)로 빌드한다.
# 사용: PowerShell에서  .\build_kospi200_exe.ps1
# 결과: dist\Kospi200Crawler.exe  (파이썬이 없는 PC에서도 실행 가능)
#       dist\Kospi200Crawler.zip  (배포용 압축본)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "가상환경(.venv)이 없어 새로 만듭니다..."
    python -m venv .venv
}

& $python -m pip install --quiet -r requirements.txt pyinstaller

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name Kospi200Crawler `
    --icon app.ico `
    --add-data "app.ico;." `
    --exclude-module tkinter `
    --exclude-module pandas `
    --exclude-module numpy `
    --exclude-module matplotlib `
    kospi200_crawler.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 빌드 실패" }

Compress-Archive -Path "dist\Kospi200Crawler.exe" -DestinationPath "dist\Kospi200Crawler.zip" -Force

Write-Host ""
Write-Host "완료: $PSScriptRoot\dist\Kospi200Crawler.exe"
Write-Host "배포: $PSScriptRoot\dist\Kospi200Crawler.zip"

# 네이버 뉴스 크롤러를 Windows 실행파일(.exe)로 빌드한다.
# 사용: PowerShell에서  .\build_exe.ps1
# 결과: dist\NaverNewsCrawler.exe  (파이썬이 없는 PC에서도 실행 가능)

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
    --name NaverNewsCrawler `
    --icon app.ico `
    --add-data "app.ico;." `
    naver_news_crawler.py

Write-Host ""
Write-Host "완료: $PSScriptRoot\dist\NaverNewsCrawler.exe"

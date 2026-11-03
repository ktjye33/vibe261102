# 컬리 후기 감성 분석기를 Windows 실행파일(.exe)로 빌드한다.
# 사용: PowerShell에서  .\build_kurly_exe.ps1
# 결과: dist\KurlyReviewAnalyzer.exe  (파이썬이 없는 PC에서도 실행 가능)
#       dist\KurlyReviewAnalyzer.zip  (배포용 압축본)

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
    --name KurlyReviewAnalyzer `
    --icon app.ico `
    --add-data "app.ico;." `
    --exclude-module tkinter `
    --exclude-module matplotlib.backends.backend_tkagg `
    --exclude-module IPython `
    kurly_review\kurly_review_analyzer.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 빌드 실패" }

Compress-Archive -Path "dist\KurlyReviewAnalyzer.exe" -DestinationPath "dist\KurlyReviewAnalyzer.zip" -Force

Write-Host ""
Write-Host "완료: $PSScriptRoot\dist\KurlyReviewAnalyzer.exe"
Write-Host "배포: $PSScriptRoot\dist\KurlyReviewAnalyzer.zip"

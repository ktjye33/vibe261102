# S&P 500 분석기를 Windows 실행파일(.exe)로 빌드한다.
# 사용: PowerShell에서  .\build_sp500_exe.ps1
# 결과: dist\SP500Analyzer.exe  (파이썬이 없는 PC에서도 실행 가능, 데이터 CSV 내장)
#       dist\SP500Analyzer.zip  (배포용 압축본)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "가상환경(.venv)이 없어 새로 만듭니다..."
    python -m venv .venv
}

& $python -m pip install --quiet -r requirements.txt pyinstaller

# 기본 데이터: 프로젝트 폴더의 CSV를 exe 안에 묶는다 (없으면 수업 자료 폴더에서 찾음)
$csvName = "S&P 500 과거 데이터.csv"
$csv = Join-Path $PSScriptRoot $csvName
if (-not (Test-Path -LiteralPath $csv)) {
    $csv = "C:\이지예\외근\교육자료\생산성본부_바이브코딩수업\DataSet\$csvName"
}
if (-not (Test-Path -LiteralPath $csv)) { throw "데이터 파일을 찾을 수 없습니다: $csvName" }

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name SP500Analyzer `
    --icon app.ico `
    --add-data "${csv};." `
    --exclude-module tkinter `
    --exclude-module matplotlib.backends.backend_tkagg `
    --exclude-module IPython `
    sp500_analysis.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 빌드 실패" }

Compress-Archive -Path "dist\SP500Analyzer.exe" -DestinationPath "dist\SP500Analyzer.zip" -Force

Write-Host ""
Write-Host "완료: $PSScriptRoot\dist\SP500Analyzer.exe"
Write-Host "배포: $PSScriptRoot\dist\SP500Analyzer.zip"

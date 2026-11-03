# 대한민국 출생아수 분석기를 Windows 실행파일(.exe)로 빌드한다.
# 사용: PowerShell에서  .\build_birth_exe.ps1
# 결과: dist\BirthAnalyzer.exe  (파이썬이 없는 PC에서도 실행 가능, 데이터 엑셀 내장)
#       dist\BirthAnalyzer.zip  (배포용 압축본)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "가상환경(.venv)이 없어 새로 만듭니다..."
    python -m venv .venv
}

& $python -m pip install --quiet -r requirements.txt pyinstaller

# 기본 데이터: 앱 폴더의 엑셀을 exe 안에 묶는다 (없으면 수업 자료 폴더에서 찾음)
$xlsxName = "출생아수__합계출산율__자연증가_등_20260605082440.xlsx"
$xlsx = Join-Path $PSScriptRoot "birth_analysis\$xlsxName"
if (-not (Test-Path -LiteralPath $xlsx)) {
    $xlsx = "C:\이지예\외근\교육자료\생산성본부_바이브코딩수업\DataSet\$xlsxName"
}
if (-not (Test-Path -LiteralPath $xlsx)) { throw "데이터 파일을 찾을 수 없습니다: $xlsxName" }

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name BirthAnalyzer `
    --icon app.ico `
    --add-data "${xlsx};." `
    --exclude-module tkinter `
    --exclude-module matplotlib.backends.backend_tkagg `
    --exclude-module IPython `
    birth_analysis\birth_analysis.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 빌드 실패" }

Compress-Archive -Path "dist\BirthAnalyzer.exe" -DestinationPath "dist\BirthAnalyzer.zip" -Force

Write-Host ""
Write-Host "완료: $PSScriptRoot\dist\BirthAnalyzer.exe"
Write-Host "배포: $PSScriptRoot\dist\BirthAnalyzer.zip"

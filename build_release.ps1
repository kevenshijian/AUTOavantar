# AUTOavantar 打包发布脚本
# 用于构建 Windows 发行版

param(
    [string]$Version = "1.1.0",
    [switch]$Clean = $false
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AUTOavantar 打包发布脚本" -ForegroundColor Cyan
Write-Host "  版本: $Version" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 Python 环境
$PythonPath = Join-Path $ProjectRoot "py310\python.exe"
if (-not (Test-Path $PythonPath)) {
    Write-Host "[错误] 未找到 Python 环境: $PythonPath" -ForegroundColor Red
    exit 1
}

# 清理旧文件
if ($Clean) {
    Write-Host "[清理] 删除旧的打包文件..." -ForegroundColor Yellow
    $BuildPath = Join-Path $ProjectRoot "build"
    $DistPath = Join-Path $ProjectRoot "dist"
    if (Test-Path $BuildPath) { Remove-Item -Recurse -Force $BuildPath }
    if (Test-Path $DistPath) { Remove-Item -Recurse -Force $DistPath }
}

# 构建前端
Write-Host "[构建] 编译前端..." -ForegroundColor Green
$FrontendPath = Join-Path $ProjectRoot "frontend"
Set-Location $FrontendPath
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] 前端构建失败" -ForegroundColor Red
    exit 1
}

# 打包后端
Write-Host "[打包] 使用 PyInstaller 打包..." -ForegroundColor Green
Set-Location $ProjectRoot

$PyInstallerArgs = @(
    "desktop_launcher.py",
    "--name", "AUTOavantar",
    "--onefile",
    "--windowed",
    "--add-data", "frontend/dist;frontend/dist",
    "--add-data", "config;config",
    "--add-data", "Portrait;Portrait",
    "--add-data", "voicel;voicel",
    "--add-data", "engines;engines",
    "--hidden-import", "uvicorn",
    "--hidden-import", "fastapi",
    "--hidden-import", "pydantic",
    "--distpath", "dist",
    "--workpath", "build"
)

& $PythonPath -m PyInstaller @PyInstallerArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] 打包失败" -ForegroundColor Red
    exit 1
}

# 创建发布包
Write-Host "[发布] 创建发布包..." -ForegroundColor Green
$ReleasePath = Join-Path $ProjectRoot "release\installer"
if (-not (Test-Path $ReleasePath)) {
    New-Item -ItemType Directory -Path $ReleasePath -Force | Out-Null
}

$OutputZip = Join-Path $ReleasePath "AUTOavantar-$Version.zip"
$DistPath = Join-Path $ProjectRoot "dist"

# 复制必要文件到 dist 目录
Copy-Item -Path "启动系统.bat" -Destination $DistPath
Copy-Item -Path "README.md" -Destination $DistPath -ErrorAction SilentlyContinue

# 创建 ZIP 包
Compress-Archive -Path "$DistPath\*" -DestinationPath $OutputZip -Force

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  打包完成！" -ForegroundColor Green
Write-Host "  输出文件: $OutputZip" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

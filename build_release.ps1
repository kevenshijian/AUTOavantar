# AUTOavantar 打包发布脚本
# 用于构建 Windows 发行版
#
# 流程说明：
# 1. PyInstaller 打包 desktop_launcher.py 成 AUTOavantar.exe（轻量级启动器）
# 2. 复制文件到 release/AUTOavantar-{version}/ 目录
# 3. 开发者自行压缩发布

param(
    [string]$Version = "",
    [switch]$Clean = $false
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

# 读取版本号
if ($Version -eq "") {
    $VersionFile = Join-Path $ProjectRoot "VERSION"
    if (Test-Path $VersionFile) {
        $Version = (Get-Content $VersionFile -Raw).Trim()
    } else {
        $Version = "1.1.0"
    }
}

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

# 检查前端构建
$FrontendDist = Join-Path $ProjectRoot "frontend\dist\index.html"
if (-not (Test-Path $FrontendDist)) {
    Write-Host "[构建] 前端未构建，正在构建..." -ForegroundColor Yellow
    Set-Location (Join-Path $ProjectRoot "frontend")
    npm run build
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[错误] 前端构建失败" -ForegroundColor Red
        exit 1
    }
    Set-Location $ProjectRoot
}

# 清理旧文件
if ($Clean) {
    Write-Host "[清理] 删除旧的打包文件..." -ForegroundColor Yellow
    $BuildPath = Join-Path $ProjectRoot "build"
    $DistPath = Join-Path $ProjectRoot "dist"
    if (Test-Path $BuildPath) { Remove-Item -Recurse -Force $BuildPath }
    if (Test-Path $DistPath) { Remove-Item -Recurse -Force $DistPath }
}

# Step 1: 使用 PyInstaller 打包启动器
Write-Host "[打包] 使用 PyInstaller 打包启动器..." -ForegroundColor Green

& $PythonPath -m PyInstaller --clean desktop_launcher.spec

if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] PyInstaller 打包失败" -ForegroundColor Red
    exit 1
}

# Step 2: 创建分发目录
Write-Host "[发布] 创建分发目录..." -ForegroundColor Green
$ReleaseDir = Join-Path $ProjectRoot "release\AUTOavantar-$Version"
if (Test-Path $ReleaseDir) {
    Remove-Item -Recurse -Force $ReleaseDir
}
New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null

# Step 3: 复制文件
Write-Host "[复制] 复制必要文件..." -ForegroundColor Green

# 复制启动器 exe
$ExePath = Join-Path $ProjectRoot "dist\AUTOavantar.exe"
if (Test-Path $ExePath) {
    Copy-Item $ExePath $ReleaseDir
    Write-Host "  复制: AUTOavantar.exe" -ForegroundColor Gray
} else {
    Write-Host "[错误] 未找到打包后的 exe: $ExePath" -ForegroundColor Red
    exit 1
}

# 复制图标
Copy-Item (Join-Path $ProjectRoot "favicon.ico") $ReleaseDir -ErrorAction SilentlyContinue

# 复制 VERSION 文件
Copy-Item (Join-Path $ProjectRoot "VERSION") $ReleaseDir

# 复制启动脚本（备用启动方式）
Copy-Item (Join-Path $ProjectRoot "启动系统.bat") $ReleaseDir -ErrorAction SilentlyContinue

# 复制目录（排除不必要的文件）
$DirsToCopy = @(
    @{Src="backend"; Dest="backend"; Exclude=@("__pycache__", "*.pyc", "data", "logs", "temp")},
    @{Src="business"; Dest="business"; Exclude=@("__pycache__", "*.pyc")},
    @{Src="core"; Dest="core"; Exclude=@("__pycache__", "*.pyc", "tests")},
    @{Src="config"; Dest="config"; Exclude=@("license\private_key.pem")},
    @{Src="frontend\dist"; Dest="frontend\dist"; Exclude=@()},
    @{Src="py310"; Dest="py310"; Exclude=@("Tools", "*.pdb", "__pycache__")},
    @{Src="Portrait"; Dest="Portrait"; Exclude=@()},
    @{Src="voicel"; Dest="voicel"; Exclude=@()},
    @{Src="engines"; Dest="engines"; Exclude=@()}
)

foreach ($Dir in $DirsToCopy) {
    $SrcPath = Join-Path $ProjectRoot $Dir.Src
    $DestPath = Join-Path $ReleaseDir $Dir.Dest

    if (Test-Path $SrcPath) {
        Write-Host "  复制: $($Dir.Src)" -ForegroundColor Gray
        Copy-Item -Path $SrcPath -Destination $DestPath -Recurse -Force

        # 删除排除的文件/目录
        foreach ($Exclude in $Dir.Exclude) {
            $ExcludePath = Join-Path $DestPath $Exclude
            if (Test-Path $ExcludePath) {
                Remove-Item -Recurse -Force $ExcludePath -ErrorAction SilentlyContinue
            }
        }
    }
}

# 清理 __pycache__ 目录
Get-ChildItem -Path $ReleaseDir -Directory -Recurse -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# 删除 .pyc 文件
Get-ChildItem -Path $ReleaseDir -File -Recurse -Filter "*.pyc" | Remove-Item -Force -ErrorAction SilentlyContinue

# 删除 .pdb 文件
Get-ChildItem -Path $ReleaseDir -File -Recurse -Filter "*.pdb" | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  打包完成！" -ForegroundColor Green
Write-Host "  输出目录: $ReleaseDir" -ForegroundColor Green
Write-Host "  请自行压缩该目录发布" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green

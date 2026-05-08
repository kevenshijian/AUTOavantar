# AUTOavantar 打包发布脚本
# 用于构建 Windows 发行版
#
# 流程说明：
# 1. 清理前端 dist 目录
# 2. 编译前端
# 3. PyInstaller 打包 desktop_launcher.py 成 AUTOavantar.exe
# 4. 复制文件到 release/AUTOavantar-{version}/ 目录
# 5. 开发者自行压缩发布

param(
    [string]$Version = "",
    [switch]$Clean = $false,
    [switch]$SkipFrontend = $false
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

# Step 1: 清理并编译前端
if (-not $SkipFrontend) {
    $FrontendDistDir = Join-Path $ProjectRoot "frontend\dist"

    # 清理前端 dist 目录
    Write-Host "[清理] 清理前端 dist 目录..." -ForegroundColor Yellow
    if (Test-Path $FrontendDistDir) {
        Remove-Item -Recurse -Force $FrontendDistDir
        Write-Host "  已删除: $FrontendDistDir" -ForegroundColor Gray
    }

    # 编译前端
    Write-Host "[构建] 编译前端..." -ForegroundColor Green
    Set-Location (Join-Path $ProjectRoot "frontend")
    npm run build
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[错误] 前端构建失败" -ForegroundColor Red
        Set-Location $ProjectRoot
        exit 1
    }
    Set-Location $ProjectRoot
    Write-Host "[完成] 前端编译完成" -ForegroundColor Green
} else {
    Write-Host "[跳过] 跳过前端编译（使用 -SkipFrontend 参数）" -ForegroundColor Yellow
}

# 清理旧的打包文件
Write-Host "[清理] 删除旧的打包文件..." -ForegroundColor Yellow
$BuildPath = Join-Path $ProjectRoot "build"
$DistPath = Join-Path $ProjectRoot "dist"
if (Test-Path $BuildPath) { Remove-Item -Recurse -Force $BuildPath }
if (Test-Path $DistPath) { Remove-Item -Recurse -Force $DistPath }

# 清理 PyInstaller 缓存
$PyInstallerCache = Join-Path $env:LOCALAPPDATA "pyinstaller"
if (Test-Path $PyInstallerCache) {
    Remove-Item -Recurse -Force $PyInstallerCache -ErrorAction SilentlyContinue
    Write-Host "  已清理 PyInstaller 缓存" -ForegroundColor Gray
}

# Step 2: 使用 PyInstaller 打包启动器
Write-Host "[打包] 使用 PyInstaller 打包启动器..." -ForegroundColor Green

# 设置错误操作偏好，避免 stderr 被视为错误
$ErrorActionPreference = "Continue"

# 运行 PyInstaller
# 注意：PyInstaller 将 INFO 日志输出到 stderr，这是正常行为
$PyInstallerProcess = Start-Process -FilePath $PythonPath -ArgumentList @(
    "-m", "PyInstaller", "desktop_launcher.spec", "--noconfirm"
) -NoNewWindow -Wait -PassThru -RedirectStandardOutput "$env:TEMP\pyinstaller_out.log" -RedirectStandardError "$env:TEMP\pyinstaller_err.log"

# 读取日志（用于调试）
$PyInstallerOut = Get-Content "$env:TEMP\pyinstaller_out.log" -ErrorAction SilentlyContinue
$PyInstallerErr = Get-Content "$env:TEMP\pyinstaller_err.log" -ErrorAction SilentlyContinue

# 显示关键日志（过滤 ANSI 颜色代码）
if ($PyInstallerErr) {
    $PyInstallerErr | ForEach-Object {
        $cleanLine = $_ -replace '\x1b\[[0-9;]*m', ''
        # 只显示 WARNING 和 ERROR 级别的日志
        if ($cleanLine -match "WARNING|ERROR|failed|Failed|FAILED") {
            Write-Host "  $cleanLine" -ForegroundColor Yellow
        }
    }
}

# 检查 PyInstaller 退出码
if ($PyInstallerProcess.ExitCode -ne 0) {
    Write-Host "[错误] PyInstaller 返回错误码: $($PyInstallerProcess.ExitCode)" -ForegroundColor Red
    # 显示完整错误日志
    if ($PyInstallerErr) {
        Write-Host "PyInstaller 错误日志:" -ForegroundColor Gray
        $PyInstallerErr | ForEach-Object {
            Write-Host "  $($_ -replace '\x1b\[[0-9;]*m', '')" -ForegroundColor Gray
        }
    }
    exit 1
}

# 检查 exe 是否生成
$ExePath = Join-Path $ProjectRoot "dist\AUTOavantar.exe"
if (-not (Test-Path $ExePath)) {
    Write-Host "[错误] PyInstaller 打包失败，未生成 exe" -ForegroundColor Red
    Write-Host "  预期路径: $ExePath" -ForegroundColor Gray
    Write-Host "  dist 目录内容:" -ForegroundColor Gray
    Get-ChildItem (Join-Path $ProjectRoot "dist") -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "    - $($_.Name)" -ForegroundColor Gray
    }
    exit 1
}

# 显示 exe 文件信息
$ExeInfo = Get-Item $ExePath
Write-Host "[完成] EXE 打包成功: $ExePath" -ForegroundColor Green
Write-Host "  文件大小: $([math]::Round($ExeInfo.Length / 1MB, 2)) MB" -ForegroundColor Gray

# Step 3: 创建分发目录
Write-Host "[发布] 创建分发目录..." -ForegroundColor Green
$ReleaseDir = Join-Path $ProjectRoot "release\AUTOavantar"
if (Test-Path $ReleaseDir) {
    Remove-Item -Recurse -Force $ReleaseDir
}
New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null

# Step 4: 复制文件
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

# 复制目录（排除私钥等敏感文件）
$DirsToCopy = @(
    @{Src="backend"; Dest="backend"},
    @{Src="business"; Dest="business"},
    @{Src="core"; Dest="core"},
    @{Src="config"; Dest="config"},
    @{Src="frontend\dist"; Dest="frontend\dist"},
    @{Src="py310"; Dest="py310"},
    @{Src="voicel"; Dest="voicel"},
    @{Src="tools"; Dest="tools"},
    @{Src="engines"; Dest="engines"}
)

# 敏感文件黑名单（安全：绝不打包到发布版本）
$SensitiveFiles = @(
    "private_key.pem",
    "*.private.key",
    "*.secret",
    ".env",
    ".env.local",
    ".env.*.local"
)

foreach ($Dir in $DirsToCopy) {
    $SrcPath = Join-Path $ProjectRoot $Dir.Src
    $DestPath = Join-Path $ReleaseDir $Dir.Dest

    if (Test-Path $SrcPath) {
        Write-Host "  复制: $($Dir.Src)" -ForegroundColor Gray
        Copy-Item -Path $SrcPath -Destination $DestPath -Recurse -Force

        # 删除敏感文件
        foreach ($Pattern in $SensitiveFiles) {
            Get-ChildItem -Path $DestPath -Recurse -Filter $Pattern -ErrorAction SilentlyContinue | ForEach-Object {
                Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
                Write-Host "    [安全] 已排除敏感文件: $($_.Name)" -ForegroundColor Yellow
            }
        }
    }
}

# 仅清理 __pycache__ 目录（这些是 Python 自动生成的缓存，不影响运行）
Get-ChildItem -Path $ReleaseDir -Directory -Recurse -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  打包完成！" -ForegroundColor Green
Write-Host "  输出目录: $ReleaseDir" -ForegroundColor Green
Write-Host "  请自行压缩该目录发布" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green

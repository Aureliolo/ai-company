# SynthOrg CLI installer for Windows.
# Usage: irm https://synthorg.io/get/install.ps1 | iex
#
# Environment variables:
#   SYNTHORG_VERSION  -- specific version to install (default: latest)
#   INSTALL_DIR       -- installation directory (default: $env:LOCALAPPDATA\synthorg\bin)

$ErrorActionPreference = "Stop"

$Repo = "Aureliolo/synthorg"
$BinaryName = "synthorg.exe"
$InstallDir = if ($env:INSTALL_DIR) { $env:INSTALL_DIR } else { Join-Path $env:LOCALAPPDATA "synthorg\bin" }

# --- Colors (ANSI true-color, matches CLI palette) ---

$NoColor = $env:NO_COLOR -or [System.Console]::IsOutputRedirected
if (-not $NoColor) {
    $C_Blue    = "`e[38;2;56;189;248m"
    $C_Green   = "`e[38;2;52;211;153m"
    $C_Red     = "`e[38;2;248;113;113m"
    $C_Dim     = "`e[2m"
    $C_Bold    = "`e[1m"
    $C_Reset   = "`e[0m"
} else {
    $C_Blue = ""; $C_Green = ""; $C_Red = ""; $C_Dim = ""; $C_Bold = ""; $C_Reset = ""
}

function Step($N, $Total, $Msg) { Write-Host "${C_Blue}[${N}/${Total}]${C_Reset} ${Msg}" }
function Fail($Msg) { [Console]::Error.WriteLine("${C_Red}error: ${Msg}${C_Reset}"); exit 1 }

$Total = 4

# --- Resolve version ---

if (-not $env:SYNTHORG_VERSION) {
    Step 1 $Total "Fetching latest release..."
    $Release = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest"
    $Version = $Release.tag_name
} else {
    Step 1 $Total "Using specified version..."
    $Version = $env:SYNTHORG_VERSION
}

# Validate version string to prevent injection.
if ($Version -notmatch '^v\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$') {
    Fail "invalid version string: $Version"
}

# --- Detect architecture ---

$OsArch = $null
try {
    $OsArch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture
} catch {
    Write-Verbose "RuntimeInformation unavailable; using PROCESSOR_ARCHITECTURE fallback."
}

if ($null -ne $OsArch) {
    $WinArch = switch ($OsArch) {
        ([System.Runtime.InteropServices.Architecture]::X64)   { "amd64" }
        ([System.Runtime.InteropServices.Architecture]::Arm64) { "arm64" }
        default { Fail "unsupported architecture: $OsArch" }
    }
} else {
    $ArchEnv = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
    $WinArch = switch ($ArchEnv) {
        "AMD64" { "amd64" }
        "ARM64" { "arm64" }
        default { Fail "unsupported architecture: $ArchEnv" }
    }
}

Write-Host "  ${C_Dim}Platform:${C_Reset} windows/$WinArch  ${C_Dim}Version:${C_Reset} $Version"

# --- Download ---

$ArchiveName = "synthorg_windows_$WinArch.zip"
$DownloadUrl = "https://github.com/$Repo/releases/download/$Version/$ArchiveName"
$ChecksumsUrl = "https://github.com/$Repo/releases/download/$Version/checksums.txt"

$TmpDir = Join-Path $env:TEMP "synthorg-install-$(Get-Random)"
New-Item -ItemType Directory -Path $TmpDir -Force | Out-Null

try {
    Step 2 $Total "Downloading..."
    Invoke-WebRequest -Uri $DownloadUrl -OutFile (Join-Path $TmpDir $ArchiveName)
    Invoke-WebRequest -Uri $ChecksumsUrl -OutFile (Join-Path $TmpDir "checksums.txt")

    # --- Verify checksum ---

    Step 3 $Total "Verifying checksum..."
    $line = Get-Content (Join-Path $TmpDir "checksums.txt") |
        Where-Object { ($_ -split '\s+')[1] -eq $ArchiveName } |
        Select-Object -First 1

    if (-not $line) {
        Fail "no checksum found for $ArchiveName"
    }
    $ExpectedHash = ($line -split '\s+')[0].Trim().ToLower()

    $ActualHash = (Get-FileHash -Path (Join-Path $TmpDir $ArchiveName) -Algorithm SHA256).Hash.ToLower()

    if ($ExpectedHash -ne $ActualHash) {
        Write-Host "  ${C_Red}Expected: $ExpectedHash${C_Reset}"
        Write-Host "  ${C_Red}Actual:   $ActualHash${C_Reset}"
        Fail "checksum mismatch"
    }

    # --- Extract and install ---

    Step 4 $Total "Installing to $InstallDir..."
    Expand-Archive -Path (Join-Path $TmpDir $ArchiveName) -DestinationPath $TmpDir -Force
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    Move-Item -Path (Join-Path $TmpDir $BinaryName) -Destination (Join-Path $InstallDir $BinaryName) -Force

    # Add to PATH if not already there (exact entry match, not substring).
    $NormalizedInstallDir = $InstallDir.TrimEnd('\')
    $UserPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    $UserPathEntries = ($UserPath -split ';') | ForEach-Object { $_.TrimEnd('\') } | Where-Object { $_ }
    if ($UserPathEntries -notcontains $NormalizedInstallDir) {
        $NewUserPath = if ($UserPath) { "$UserPath;$InstallDir" } else { $InstallDir }
        [Environment]::SetEnvironmentVariable("PATH", $NewUserPath, "User")
    }
    $ProcessPathEntries = ($env:PATH -split ';') | ForEach-Object { $_.TrimEnd('\') } | Where-Object { $_ }
    if ($ProcessPathEntries -notcontains $NormalizedInstallDir) {
        $env:PATH = "$env:PATH;$InstallDir"
    }

    # --- Done ---

    Write-Host ""
    Write-Host "${C_Green}SynthOrg CLI installed${C_Reset} ${C_Dim}($Version)${C_Reset}"
    Write-Host ""
    Write-Host "  ${C_Blue}Next:${C_Reset} ${C_Bold}synthorg init${C_Reset}"
    Write-Host ""
} finally {
    Remove-Item -Path $TmpDir -Recurse -Force -ErrorAction SilentlyContinue
}

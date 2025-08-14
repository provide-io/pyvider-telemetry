# env.ps1 - pyvider-telemetry Development Environment Setup
#
# This script sets up a clean, isolated development environment for pyvider-telemetry
# using 'uv' for high-performance virtual environment and dependency management.
#
# Usage: .\env.ps1
#

# --- Configuration ---
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Helper functions for formatted output
function Write-Header {
    param([string]$Message)
    Write-Host "`n--- $Message ---" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "✅ $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "❌ $Message" -ForegroundColor Red
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠️  $Message" -ForegroundColor Yellow
}
# --- Cleanup Previous Environment ---
Write-Header "🧹 Cleaning Previous Environment"

# Remove any existing Python aliases
Remove-Alias -Name python -ErrorAction SilentlyContinue
Remove-Alias -Name python3 -ErrorAction SilentlyContinue
Remove-Alias -Name pip -ErrorAction SilentlyContinue
Remove-Alias -Name pip3 -ErrorAction SilentlyContinue

# Clear existing PYTHONPATH
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue

# Store original PATH for restoration if needed
$script:OriginalPath = $env:PATH

Write-Success "Cleared Python aliases and PYTHONPATH"
# --- Project Validation ---
if (-not (Test-Path "pyproject.toml")) {
    Write-Error "No 'pyproject.toml' found in current directory"
    Write-Host "Please run this script from the pyvider-telemetry root directory"
    exit 1
}

$ProjectName = Split-Path -Leaf (Get-Location)

# --- UV Installation ---
Write-Header "🚀 Checking UV Package Manager"

$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvCommand) {
    Write-Host "Installing UV..."
    
    # Install UV using the official PowerShell installer
    try {
        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
        
        # Refresh PATH
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "User")
        
        # Check if UV is now available
        $uvCommand = Get-Command uv -ErrorAction SilentlyContinue
        if ($uvCommand) {
            Write-Success "UV installed successfully"
        } else {
            Write-Error "UV installation failed"
            exit 1
        }
    }
    catch {
        Write-Error "UV installation failed: $_"
        exit 1
    }
} else {
    Write-Success "UV already installed"
}
# --- Platform Detection ---
$TFOS = if ($IsWindows) { "windows" } elseif ($IsMacOS) { "darwin" } else { "linux" }
$TFARCH = switch ([System.Environment]::Is64BitOperatingSystem) {
    $true { 
        if ([System.Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture -eq [System.Runtime.InteropServices.Architecture]::Arm64) {
            "arm64"
        } else {
            "amd64"
        }
    }
    $false { "386" }
}

# Workenv directory setup
$Profile = if ($env:PYVIDER_TELEMETRY_PROFILE) { $env:PYVIDER_TELEMETRY_PROFILE } else { "default" }
if ($Profile -eq "default") {
    $VenvDir = "workenv/pyvider-telemetry_${TFOS}_${TFARCH}"
} else {
    $VenvDir = "workenv/${Profile}_${TFOS}_${TFARCH}"
}

$env:UV_PROJECT_ENVIRONMENT = $VenvDir
# --- Virtual Environment ---
Write-Header "🐍 Setting Up Virtual Environment"
Write-Host "Directory: $VenvDir"

# Check for existing venv - handle cross-platform paths
if ($IsWindows) {
    $VenvExists = (Test-Path $VenvDir) -and (Test-Path "$VenvDir/Scripts/activate.ps1") -and (Test-Path "$VenvDir/Scripts/python.exe")
} else {
    $VenvExists = (Test-Path $VenvDir) -and (Test-Path "$VenvDir/bin/activate.ps1") -and (Test-Path "$VenvDir/bin/python")
}

if ($VenvExists) {
    Write-Success "Virtual environment exists"
} else {
    Write-Host "Creating virtual environment..." -NoNewline
    try {
        & uv venv $VenvDir
        Write-Success " Virtual environment created"
    }
    catch {
        Write-Error " Virtual environment creation failed: $_"
        exit 1
    }
}

# Activate virtual environment - handle cross-platform paths
if ($IsWindows) {
    $ActivateScript = Join-Path $VenvDir "Scripts/Activate.ps1"
} else {
    # On macOS/Linux, activation script is in bin directory with lowercase name
    $ActivateScript = Join-Path $VenvDir "bin/activate.ps1"
}

if (Test-Path $ActivateScript) {
    & $ActivateScript
    $env:VIRTUAL_ENV = Join-Path (Get-Location) $VenvDir
} else {
    Write-Error "Could not find activation script at $ActivateScript"
    Write-Host "Note: Virtual environment created but activation failed."
    Write-Host "For macOS/Linux, you may need to use: source $VenvDir/bin/activate"
    exit 1
}
# --- Dependency Installation ---
Write-Header "📦 Installing Dependencies"

# Create log directory
$LogDir = Join-Path $env:TEMP "pyvider-telemetry_setup"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

Write-Host "Syncing dependencies..." -NoNewline
try {
    & uv sync --all-groups 2>&1 | Out-File -FilePath (Join-Path $LogDir "sync.log")
    Write-Success " Dependencies synced"
}
catch {
    Write-Error " Dependency sync failed"
    Write-Host "Check log at: $(Join-Path $LogDir 'sync.log')"
    exit 1
}

Write-Host "Installing pyvider-telemetry in editable mode..." -NoNewline
try {
    & uv pip install --no-deps -e . 2>&1 | Out-File -FilePath (Join-Path $LogDir "install.log")
    Write-Success " pyvider-telemetry installed"
}
catch {
    Write-Error " Installation failed"
    Write-Host "Check log at: $(Join-Path $LogDir 'install.log')"
    exit 1
}
# --- Sibling Packages ---
Write-Header "🤝 Installing Sibling Packages"

$ParentDir = Split-Path -Parent (Get-Location)
$SiblingCount = 0


if ($SiblingCount -eq 0) {
    Write-Warning "No sibling packages found"
}
# --- Environment Configuration ---
Write-Header "🔧 Configuring Environment"

# Set clean PYTHONPATH
$env:PYTHONPATH = "$(Get-Location)/src;$(Get-Location)"
Write-Host "PYTHONPATH: $env:PYTHONPATH"

# Clean up PATH - remove duplicates and handle cross-platform
if ($IsWindows) {
    $PathSeparator = ';'
    $VenvBin = Join-Path $VenvDir "Scripts"
} else {
    $PathSeparator = ':'
    $VenvBin = Join-Path $VenvDir "bin"
}

$PathArray = $env:PATH -split $PathSeparator | Where-Object { $_ -ne '' } | Select-Object -Unique
$NewPath = @($VenvBin) + ($PathArray | Where-Object { $_ -ne $VenvBin })
$env:PATH = $NewPath -join $PathSeparator

# --- Tool Verification ---
Write-Header "🔍 Verifying Installation"

Write-Host "`nTool Locations & Versions:" -ForegroundColor Green
Write-Host ("━" * 40)

# Python
$PYTHONCmd = Get-Command python -ErrorAction SilentlyContinue
if ($PYTHONCmd) {
    Write-Host ("{0,-12}: {1}" -f "Python", $PYTHONCmd.Source)
    $Version = & python --version 2>&1 2>&1 | Select-Object -First 1
    Write-Host ("{0,-12}  {1}" -f "", $Version)
}

# UV
$UVCmd = Get-Command uv -ErrorAction SilentlyContinue
if ($UVCmd) {
    Write-Host ("{0,-12}: {1}" -f "UV", $UVCmd.Source)
    $Version = & uv --version 2>&1 2>&1 | Select-Object -First 1
    Write-Host ("{0,-12}  {1}" -f "", $Version)
}

# wrkenv
$WRKENVCmd = Get-Command wrkenv -ErrorAction SilentlyContinue
if ($WRKENVCmd) {
    Write-Host ("{0,-12}: {1}" -f "wrkenv", $WRKENVCmd.Source)
    $Version = & wrkenv --version 2>&1 || echo 'No version info' 2>&1 | Select-Object -First 1
    Write-Host ("{0,-12}  {1}" -f "", $Version)
}

# ibmtf
$IBMTFCmd = Get-Command ibmtf -ErrorAction SilentlyContinue
if ($IBMTFCmd) {
    Write-Host ("{0,-12}: {1}" -f "ibmtf", $IBMTFCmd.Source)
    $Version = & ibmtf version 2>&1 | head -1 || echo 'Not installed' 2>&1 | Select-Object -First 1
    Write-Host ("{0,-12}  {1}" -f "", $Version)
}

# tofu
$TOFUCmd = Get-Command tofu -ErrorAction SilentlyContinue
if ($TOFUCmd) {
    Write-Host ("{0,-12}: {1}" -f "tofu", $TOFUCmd.Source)
    $Version = & tofu version 2>&1 | head -1 || echo 'Not installed' 2>&1 | Select-Object -First 1
    Write-Host ("{0,-12}  {1}" -f "", $Version)
}


Write-Host ("━" * 40)
# --- Final Summary ---
Write-Header "✅ Environment Ready!"

Write-Host "`n$("pyvider-telemetry development environment activated" | Write-Host -ForegroundColor Green)"
Write-Host "Virtual environment: $VenvDir"
Write-Host "Profile: $Profile"
Write-Host "`nUseful commands:"
Write-Host "  pyvider-telemetry --help  # pyvider-telemetry CLI"
Write-Host "  wrkenv status  # Check tool versions"
Write-Host "  wrkenv container status  # Container status"
Write-Host "  pytest  # Run tests"
Write-Host "  deactivate  # Exit environment"

# --- Cleanup ---
# Remove temporary log files older than 1 day
if (Test-Path $LogDir) {
    Get-ChildItem -Path $LogDir -Filter "*.log" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-1) } | Remove-Item -Force -ErrorAction SilentlyContinue
}

# Return success
exit 0
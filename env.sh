#!/bin/bash
#
# env.sh - pyvider-telemetry Development Environment Setup
#
# This script sets up a clean, isolated development environment for pyvider-telemetry
# using 'uv' for high-performance virtual environment and dependency management.
#
# Usage: source ./env.sh
#

# --- Configuration ---
COLOR_BLUE='\033[0;34m'
COLOR_GREEN='\033[0;32m'
COLOR_YELLOW='\033[0;33m'
COLOR_RED='\033[0;31m'
COLOR_NC='\033[0m'

# Spinner animation for long operations
spinner() {
    local pid=$1
    local delay=0.1
    local spinstr='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    while ps -p $pid > /dev/null 2>&1; do
        local temp=${spinstr#?}
        printf " [%c]  " "$spinstr"
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
        printf "\b\b\b\b\b\b"
    done
    printf "    \b\b\b\b"
}
print_header() {
    echo -e "\n${COLOR_BLUE}--- ${1} ---${COLOR_NC}"
}

print_success() {
    echo -e "${COLOR_GREEN}✅ ${1}${COLOR_NC}"
}

print_error() {
    echo -e "${COLOR_RED}❌ ${1}${COLOR_NC}"
}

print_warning() {
    echo -e "${COLOR_YELLOW}⚠️  ${1}${COLOR_NC}"
}
# --- Cleanup Previous Environment ---
print_header "🧹 Cleaning Previous Environment"

# Remove any existing Python aliases
unalias python 2>/dev/null
unalias python3 2>/dev/null
unalias pip 2>/dev/null
unalias pip3 2>/dev/null

# Clear existing PYTHONPATH
unset PYTHONPATH

# Store original PATH for restoration if needed
ORIGINAL_PATH="${PATH}"

print_success "Cleared Python aliases and PYTHONPATH"
# --- Project Validation ---
if [ ! -f "pyproject.toml" ]; then
    print_error "No 'pyproject.toml' found in current directory"
    echo "Please run this script from the pyvider-telemetry root directory"
    return 1 2>/dev/null || exit 1
fi

PROJECT_NAME=$(basename "$(pwd)")

# --- UV Installation ---
print_header "🚀 Checking UV Package Manager"

if ! command -v uv &> /dev/null; then
    echo "Installing UV..."
    curl -LsSf https://astral.sh/uv/install.sh | sh > /tmp/uv_install.log 2>&1 &
    spinner $!
    
    UV_ENV_PATH_LOCAL="$HOME/.local/bin/env"
    UV_ENV_PATH_CARGO="$HOME/.cargo/env"
    
    if [ -f "$UV_ENV_PATH_LOCAL" ]; then
        source "$UV_ENV_PATH_LOCAL"
    elif [ -f "$UV_ENV_PATH_CARGO" ]; then
        source "$UV_ENV_PATH_CARGO"
    fi
    
    if command -v uv &> /dev/null; then
        print_success "UV installed successfully"
    else
        print_error "UV installation failed. Check /tmp/uv_install.log"
        return 1 2>/dev/null || exit 1
    fi
else
    print_success "UV already installed"
fi
# --- Platform Detection ---
TFOS=$(uname -s | tr '[:upper:]' '[:lower:]')
TFARCH=$(uname -m)
case "$TFARCH" in
    x86_64) TFARCH="amd64" ;;
    aarch64|arm64) TFARCH="arm64" ;;
esac

# Workenv directory setup
PROFILE="${PYVIDER_TELEMETRY_PROFILE:-default}"
if [ "$PROFILE" = "default" ]; then
    VENV_DIR="workenv/pyvider-telemetry_${TFOS}_${TFARCH}"
else
    VENV_DIR="workenv/${PROFILE}_${TFOS}_${TFARCH}"
fi

# Validate platform
if [[ "$TFOS" != "darwin" && "$TFOS" != "linux" ]]; then
    print_warning "Detected OS: $TFOS (only darwin and linux are fully tested)"
fi

# Set UV project environment early so uv commands use the correct venv
export UV_PROJECT_ENVIRONMENT="${VENV_DIR}"
# --- Python Version Compatibility Check ---
RECREATE_VENV=false
print_header "🐍 Checking Python Version Compatibility"

# Get project's Python requirement
PROJECT_PYTHON_REQ=">=3.11"
echo "Project requires Python ${PROJECT_PYTHON_REQ}"

# Function to check if we need to recreate venv
check_python_version() {
    local venv_dir="$1"
    local python_bin="${venv_dir}/bin/python"
    
    if [ ! -f "${python_bin}" ]; then
        return 1  # No venv exists
    fi
    
    # Get current venv Python version
    local venv_version=$("${python_bin}" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>/dev/null)
    
    if [ -z "${venv_version}" ]; then
        return 1  # Couldn't get version
    fi
    
    echo "Current venv has Python ${venv_version}"
    
    # Check if version file exists and matches
    local version_file="${venv_dir}/.python-version"
    if [ -f "${version_file}" ]; then
        local saved_version=$(cat "${version_file}")
        if [ "${saved_version}" != "${venv_version}" ]; then
            print_warning "Python version mismatch detected!"
            return 2  # Version mismatch
        fi
    fi
    
    # Check compatibility with project requirement
    "${python_bin}" -c "
import sys
from packaging.specifiers import SpecifierSet
from packaging.version import Version

requirement = '${PROJECT_PYTHON_REQ}'
current = f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}'

try:
    spec = SpecifierSet(requirement)
    version = Version(current)
    if version not in spec:
        sys.exit(1)
except:
    # If packaging is not available, do simple comparison
    import re
    match = re.match(r'>=(\d+)\.(\d+)', requirement)
    if match:
        req_major, req_minor = int(match.group(1)), int(match.group(2))
        if sys.version_info.major < req_major or (sys.version_info.major == req_major and sys.version_info.minor < req_minor):
            sys.exit(1)
" 2>/dev/null
    
    if [ $? -ne 0 ]; then
        print_warning "Python ${venv_version} does not meet requirement ${PROJECT_PYTHON_REQ}"
        return 2  # Incompatible version
    fi
    
    return 0  # All good
}

# Check if we need to recreate the venv
RECREATE_VENV=false
if [ -d "${VENV_DIR}" ]; then
    check_python_version "${VENV_DIR}"
    CHECK_RESULT=$?
    
    if [ $CHECK_RESULT -eq 2 ]; then
        RECREATE_VENV=true
        print_warning "Virtual environment needs to be recreated due to Python version mismatch"
        echo "Backing up current venv to ${VENV_DIR}.backup..."
        mv "${VENV_DIR}" "${VENV_DIR}.backup"
    fi
fi

# --- Virtual Environment ---
print_header "🐍 Setting Up Virtual Environment"
echo "Directory: ${VENV_DIR}"

if [ -d "${VENV_DIR}" ] && [ -f "${VENV_DIR}/bin/activate" ] && [ -f "${VENV_DIR}/bin/python" ] && [ "${RECREATE_VENV}" != "true" ]; then
    print_success "Virtual environment exists"
else
    if [ "${RECREATE_VENV}" = "true" ]; then
        echo -n "Recreating virtual environment with correct Python version..."
    else
        echo -n "Creating virtual environment..."
    fi
    uv venv "${VENV_DIR}" > /tmp/uv_venv.log 2>&1 &
    spinner $!
    print_success "Virtual environment created"
    
    # Save Python version for future checks
    ${VENV_DIR}/bin/python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" > "${VENV_DIR}/.python-version"
fi

# Activate virtual environment
source "${VENV_DIR}/bin/activate"
export VIRTUAL_ENV="$(pwd)/${VENV_DIR}"
export UV_PROJECT_ENVIRONMENT="${VENV_DIR}"
# --- Dependency Installation ---
print_header "📦 Installing Dependencies"

# Create log directory
mkdir -p /tmp/pyvider-telemetry_setup

echo -n "Syncing dependencies..."
uv sync --all-groups > /tmp/pyvider-telemetry_setup/sync.log 2>&1 &
SYNC_PID=$!
spinner $SYNC_PID
wait $SYNC_PID
SYNC_EXIT_CODE=$?

if [ $SYNC_EXIT_CODE -eq 0 ]; then
    print_success "Dependencies synced"
else
    print_warning "Dependency sync failed - will install project and siblings manually"
    echo "Check /tmp/pyvider-telemetry_setup/sync.log for details"
    
    # Try to install just the project without dependencies first
    echo -n "Installing pyvider-telemetry without dependencies..."
    uv pip install --no-deps -e . > /tmp/pyvider-telemetry_setup/install_nodeps.log 2>&1 &
    INSTALL_PID=$!
    spinner $INSTALL_PID
    wait $INSTALL_PID
    if [ $? -eq 0 ]; then
        print_success "pyvider-telemetry installed (no deps)"
    else
        print_error "Failed to install pyvider-telemetry"
        return 1 2>/dev/null || exit 1
    fi
fi

echo -n "Installing pyvider-telemetry in editable mode..."
uv pip install --no-deps -e . > /tmp/pyvider-telemetry_setup/install.log 2>&1 &
spinner $!
print_success "pyvider-telemetry installed"
# --- Sibling Packages ---
print_header "🤝 Installing Sibling Packages"

PARENT_DIR=$(dirname "$(pwd)")
SIBLING_COUNT=0


if [ $SIBLING_COUNT -eq 0 ]; then
    print_warning "No sibling packages found"
fi
# --- Environment Configuration ---
print_header "🔧 Configuring Environment"

# Set clean PYTHONPATH
export PYTHONPATH="${PWD}/src:${PWD}"
echo "PYTHONPATH: ${PYTHONPATH}"

# Clean up PATH - remove duplicates
# Ensure UV bin directories are included
UV_BIN_PATHS="$HOME/.local/bin:$HOME/.cargo/bin"
NEW_PATH="${VENV_DIR}/bin:${UV_BIN_PATHS}"
OLD_IFS="$IFS"
IFS=':'
for p in $PATH; do
    case ":$NEW_PATH:" in
        *":$p:"*) ;;
        *) NEW_PATH="$NEW_PATH:$p" ;;
    esac
done
IFS="$OLD_IFS"
export PATH="$NEW_PATH"

# --- Tool Verification ---
print_header "🔍 Verifying Installation"

echo -e "\n${COLOR_GREEN}Tool Locations & Versions:${COLOR_NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Python
if command -v python &> /dev/null; then
    PYTHON_PATH=$(command -v python 2>/dev/null || which python 2>/dev/null || echo "python")
    printf "%-12s: %s\n" "Python" "$PYTHON_PATH"
    printf "%-12s  %s\n" "" "$(python --version 2>&1)"
fi

# UV
if command -v uv &> /dev/null; then
    UV_PATH=$(command -v uv 2>/dev/null || which uv 2>/dev/null || echo "uv")
    printf "%-12s: %s\n" "UV" "$UV_PATH"
    printf "%-12s  %s\n" "" "$(uv --version 2>&1)"
fi

# wrkenv
if command -v wrkenv &> /dev/null; then
    WRKENV_PATH=$(command -v wrkenv 2>/dev/null || which wrkenv 2>/dev/null || echo "wrkenv")
    printf "%-12s: %s\n" "wrkenv" "$WRKENV_PATH"
    printf "%-12s  %s\n" "" "$(wrkenv --version 2>&1 || echo 'No version info')"
fi

# ibmtf
if command -v ibmtf &> /dev/null; then
    IBMTF_PATH=$(command -v ibmtf 2>/dev/null || which ibmtf 2>/dev/null || echo "ibmtf")
    printf "%-12s: %s\n" "ibmtf" "$IBMTF_PATH"
    printf "%-12s  %s\n" "" "$(ibmtf version 2>&1 | head -1 || echo 'Not installed')"
fi

# tofu
if command -v tofu &> /dev/null; then
    TOFU_PATH=$(command -v tofu 2>/dev/null || which tofu 2>/dev/null || echo "tofu")
    printf "%-12s: %s\n" "tofu" "$TOFU_PATH"
    printf "%-12s  %s\n" "" "$(tofu version 2>&1 | head -1 || echo 'Not installed')"
fi


echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
# --- Final Summary ---
print_header "✅ Environment Ready!"

echo -e "\n${COLOR_GREEN}pyvider-telemetry development environment activated${COLOR_NC}"
echo "Virtual environment: ${VENV_DIR}"
echo "Profile: ${PROFILE}"
echo -e "\nUseful commands:"
echo "  pyvider-telemetry --help  # pyvider-telemetry CLI"
echo "  wrkenv status  # Check tool versions"
echo "  wrkenv container status  # Container status"
echo "  pytest  # Run tests"
echo "  deactivate  # Exit environment"

# --- Cleanup ---
# Remove temporary log files older than 1 day
find /tmp/pyvider-telemetry_setup -name "*.log" -mtime +1 -delete 2>/dev/null

# Return success
return 0 2>/dev/null || exit 0
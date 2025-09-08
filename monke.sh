#!/usr/bin/env bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Configuration
MONKE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/monke" && pwd)"
VENV_DIR="${MONKE_DIR}/venv"
LOGS_DIR="${MONKE_DIR}/logs"
AIRWEAVE_API_URL="${AIRWEAVE_API_URL:-http://localhost:8001}"

# Usage function
usage() {
    cat << EOF
${BOLD}🐒 Monke Test Runner${NC}

${BOLD}Usage:${NC}
    ./monke.sh [connector...]           Run specific connector(s)
    ./monke.sh --changed                Run only changed connectors (vs main branch)
    ./monke.sh --all                    Run all connectors in parallel
    ./monke.sh --list                   List available connectors
    ./monke.sh --help                   Show this help

${BOLD}Examples:${NC}
    ./monke.sh github                   Run GitHub connector test
    ./monke.sh github asana notion      Run multiple specific connectors
    ./monke.sh --changed                Run tests for changed connectors only
    ./monke.sh --all                    Run all connector tests in parallel

${BOLD}Environment:${NC}
    AIRWEAVE_API_URL                    Backend URL (default: http://localhost:8001)
    MONKE_MAX_PARALLEL                  Max parallel tests (default: 5)
    MONKE_ENV_FILE                      Environment file (default: monke/env.test)
    MONKE_NO_VENV                       Skip venv setup (if set)
    MONKE_VERBOSE                       Verbose output (if set)

${BOLD}Notes:${NC}
    - Automatically sets up Python venv if needed
    - Runs tests in parallel for better performance
    - Detects changed connectors when on a feature branch
    - Logs are saved to monke/logs/
EOF
}

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ${NC}  $1"
}

log_success() {
    echo -e "${GREEN}✅${NC} $1"
}

log_error() {
    echo -e "${RED}❌${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠️${NC}  $1"
}

log_step() {
    echo -e "${CYAN}▶${NC}  $1"
}

# Check if running in CI
is_ci() {
    [[ "${CI:-}" == "true" ]] || [[ "${GITHUB_ACTIONS:-}" == "true" ]]
}

# Setup Python virtual environment
setup_venv() {
    if [[ "${MONKE_NO_VENV:-}" == "1" ]]; then
        log_info "Skipping venv setup (MONKE_NO_VENV=1)"
        return 0
    fi

    if is_ci; then
        log_info "CI environment detected, skipping venv setup"
        return 0
    fi

    if [[ ! -d "$VENV_DIR" ]]; then
        log_step "Creating Python virtual environment..."
        python3 -m venv "$VENV_DIR"
        log_success "Virtual environment created"
    fi

    log_step "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"

    # Check if requirements are installed
    if ! python -c "import airweave" 2>/dev/null; then
        log_step "Installing dependencies..."
        pip install --quiet --upgrade pip
        pip install --quiet -r "${MONKE_DIR}/requirements.txt"
        log_success "Dependencies installed"
    else
        log_info "Dependencies already installed"
    fi
}

# Get list of available connectors
get_available_connectors() {
    find "${MONKE_DIR}/configs" -name "*.yaml" -type f | \
        xargs -n1 basename | \
        sed 's/\.yaml$//' | \
        sort
}

# List available connectors
list_connectors() {
    echo -e "${BOLD}Available connectors:${NC}"
    for connector in $(get_available_connectors); do
        echo "  • $connector"
    done
}

# Detect changed connectors (vs main branch)
detect_changed_connectors() {
    local base_branch="${1:-main}"
    local changed_files
    local changed_connectors=()

    log_step "Detecting changed connectors vs ${base_branch}..."

    # Get list of changed files
    if ! git diff --name-only "${base_branch}...HEAD" &>/dev/null; then
        log_warning "Cannot detect changes (not a git repo or ${base_branch} not found)"
        return 1
    fi

    changed_files=$(git diff --name-only "${base_branch}...HEAD" | grep -E "(monke/bongos/|monke/configs/|monke/generation/|backend/airweave/entities/|backend/airweave/sources/)" || true)

    if [[ -z "$changed_files" ]]; then
        log_info "No connector-related changes detected"
        return 1
    fi

    # Extract connector names from changed files
    while IFS= read -r file; do
        local connector=""

        if [[ "$file" =~ monke/(bongos|configs|generation)/([^/]+)\.(py|yaml) ]]; then
            connector="${BASH_REMATCH[2]}"
        elif [[ "$file" =~ backend/airweave/(entities|sources)/([^/]+)\.(py|yaml) ]]; then
            connector="${BASH_REMATCH[2]}"
        fi

        if [[ -n "$connector" ]] && [[ -f "${MONKE_DIR}/configs/${connector}.yaml" ]]; then
            # Avoid duplicates
            if [[ ! " ${changed_connectors[@]} " =~ " ${connector} " ]]; then
                changed_connectors+=("$connector")
            fi
        fi
    done <<< "$changed_files"

    if [[ ${#changed_connectors[@]} -eq 0 ]]; then
        log_info "No testable connector changes detected"
        return 1
    fi

    log_success "Detected changed connectors: ${changed_connectors[*]}"
    echo "${changed_connectors[@]}"
}

# Check if Airweave backend is running
check_backend() {
    log_step "Checking Airweave backend at ${AIRWEAVE_API_URL}..."

    if curl -fsS "${AIRWEAVE_API_URL}/health" >/dev/null 2>&1; then
        log_success "Backend is healthy"
        return 0
    else
        log_error "Backend is not accessible at ${AIRWEAVE_API_URL}"
        log_info "Please ensure Airweave is running (./start.sh)"
        return 1
    fi
}

# Run tests in parallel
run_tests() {
    local connectors=("$@")
    local max_parallel="${MONKE_MAX_PARALLEL:-5}"
    local env_file="${MONKE_ENV_FILE:-${MONKE_DIR}/env.test}"

    if [[ ${#connectors[@]} -eq 0 ]]; then
        log_error "No connectors to test"
        return 1
    fi

    # Check environment file
    if [[ ! -f "$env_file" ]]; then
        log_error "Environment file not found: $env_file"
        log_info "Copy monke/env.test.example to monke/env.test and add your credentials"
        return 1
    fi

    # Create logs directory
    mkdir -p "$LOGS_DIR"
    local timestamp=$(date +%Y%m%d_%H%M%S)

    # Prepare config paths
    local config_args=""
    for connector in "${connectors[@]}"; do
        if [[ ! -f "${MONKE_DIR}/configs/${connector}.yaml" ]]; then
            log_error "Config not found for connector: $connector"
            return 1
        fi
        config_args="$config_args configs/${connector}.yaml"
    done

    log_step "Running ${#connectors[@]} connector test(s) in parallel (max $max_parallel)..."
    echo -e "${CYAN}Connectors:${NC} ${connectors[*]}"
    echo ""

    # Change to monke directory for relative paths
    cd "$MONKE_DIR"

    # Use unified runner for all cases
    python runner.py \
        "${connectors[@]}" \
        --env "$(basename "$env_file")" \
        --max-concurrency "$max_parallel" \
        --run-id-prefix "local-"

    local exit_code=$?

    # Save latest log reference
    if [[ -d "$LOGS_DIR" ]]; then
        echo "$timestamp" > "${LOGS_DIR}/.latest"
    fi

    return $exit_code
}

# Main execution
main() {
    local connectors=()
    local mode="specific"

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help|-h)
                usage
                exit 0
                ;;
            --list|-l)
                list_connectors
                exit 0
                ;;
            --all|-a)
                mode="all"
                shift
                ;;
            --changed|-c)
                mode="changed"
                shift
                ;;
            --verbose|-v)
                export MONKE_VERBOSE=1
                shift
                ;;
            --*)
                log_error "Unknown option: $1"
                usage
                exit 1
                ;;
            *)
                connectors+=("$1")
                shift
                ;;
        esac
    done

    # Header
    echo -e "${BOLD}🐒 Monke Test Runner${NC}"
    echo ""

    # Setup environment
    setup_venv

    # Check backend
    if ! is_ci; then
        check_backend || exit 1
    fi

    # Determine what to run based on mode
    case "$mode" in
        all)
            log_step "Running all connector tests..."
            connectors=($(get_available_connectors))
            ;;
        changed)
            local changed
            if changed=$(detect_changed_connectors); then
                connectors=($changed)
            else
                log_info "No tests to run"
                exit 0
            fi
            ;;
        specific)
            if [[ ${#connectors[@]} -eq 0 ]]; then
                # No arguments provided - try to detect changes
                log_info "No connectors specified, checking for changes..."
                if changed=$(detect_changed_connectors); then
                    connectors=($changed)
                else
                    log_info "No changes detected. Use --list to see available connectors"
                    exit 0
                fi
            fi
            ;;
    esac

    # Run the tests
    echo ""
    if run_tests "${connectors[@]}"; then
        echo ""
        log_success "All tests passed! 🎉"
        exit 0
    else
        echo ""
        log_error "Some tests failed. Check logs in ${LOGS_DIR}/"
        exit 1
    fi
}

# Run main function
main "$@"

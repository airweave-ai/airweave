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
AZURE_KEY_VAULT_URL="${AZURE_KEY_VAULT_URL:-}"

# Usage function
usage() {
    cat << EOF
${BOLD}🐒 Monke Test Runner${NC}

${BOLD}Usage:${NC}
    ./monke.sh [connector...]           Run specific connector(s)
    ./monke.sh --changed                Run core connectors + any changed connectors
    ./monke.sh --all                    Run all connectors in parallel
    ./monke.sh --list                   List available connectors
    ./monke.sh --print-connectors       Print connectors that would be tested (space-separated)
    ./monke.sh --help                   Show this help

${BOLD}Examples:${NC}
    ./monke.sh github                   Run GitHub connector test
    ./monke.sh github asana notion      Run multiple specific connectors
    ./monke.sh --changed                Run core + changed connectors
    ./monke.sh --all                    Run all connector tests in parallel
    ./monke.sh --print-connectors --changed  Print connectors for CI matrix

${BOLD}Environment:${NC}
    AIRWEAVE_API_URL                    Backend URL (default: http://localhost:8001)
    AZURE_KEY_VAULT_URL                 Azure Key Vault URL (optional, for secret management)
    MONKE_MAX_PARALLEL                  Max parallel tests (default: 5)
    MONKE_ENV_FILE                      Environment file (default: monke/.env)
    MONKE_NO_VENV                       Skip venv setup (if set)
    MONKE_VERBOSE                       Verbose output (if set)

${BOLD}Notes:${NC}
    - Automatically sets up Python venv if needed
    - Runs tests in parallel for better performance
    - Runs core connectors + detects additional changed connectors
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

        # Install Azure dependencies if Key Vault is configured
        if [[ -n "$AZURE_KEY_VAULT_URL" ]]; then
            log_step "Installing Azure Key Vault dependencies..."
            pip install --quiet azure-keyvault-secrets azure-identity
        fi

        log_success "Dependencies installed"
    else
        log_info "Dependencies already installed"

        # Check Azure dependencies if Key Vault is configured
        if [[ -n "$AZURE_KEY_VAULT_URL" ]] && ! python -c "import azure.keyvault.secrets" 2>/dev/null; then
            log_step "Installing Azure Key Vault dependencies..."
            pip install --quiet azure-keyvault-secrets azure-identity
        fi
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

# Get core connectors that always run
get_core_connectors() {
    local core_connectors=(
        "github"      # Most popular, good API coverage
        "asana"       # Task management, different data patterns
        "linear"      # Modern API, good for testing
        "google_docs"
    )

    # Filter to only include connectors that have configs
    local available_connectors=()
    for connector in "${core_connectors[@]}"; do
        if [[ -f "${MONKE_DIR}/configs/${connector}.yaml" ]]; then
            available_connectors+=("$connector")
        fi
    done

    echo "${available_connectors[@]}"
}

# Detect changed connectors (vs base branch)
detect_changed_connectors() {
    # Use environment variable if set, otherwise default to main
    local base_branch="${BASE_BRANCH:-${1:-main}}"
    local changed_files
    local changed_connectors=()
    local git_ref

    # In GitHub Actions, use origin/branch, locally use just branch
    if is_ci; then
        git_ref="origin/${base_branch}"
    else
        git_ref="${base_branch}"
    fi

    log_step "Detecting changed connectors vs ${git_ref}..." >&2

    # Get list of changed files
    if ! git diff --name-only "${git_ref}...HEAD" &>/dev/null; then
        log_warning "Cannot detect changes (not a git repo or ${git_ref} not found)" >&2
        return 1
    fi

    changed_files=$(git diff --name-only "${git_ref}...HEAD" | grep -E "(monke/bongos/|monke/configs/|monke/generation/|backend/airweave/platform/sources/|backend/airweave/platform/entities/)" || true)

    if [[ -z "$changed_files" ]]; then
        log_info "No connector-related changes detected" >&2
        return 1
    fi

    # Extract connector names from changed files
    while IFS= read -r file; do
        local connector=""

        # Use sed for reliable extraction (works with older bash versions)
        if echo "$file" | grep -q "monke/bongos/"; then
            connector=$(echo "$file" | sed -n 's|.*/bongos/\([^/]*\)\.py|\1|p')
        elif echo "$file" | grep -q "monke/configs/"; then
            connector=$(echo "$file" | sed -n 's|.*/configs/\([^/]*\)\.yaml|\1|p')
        elif echo "$file" | grep -q "monke/generation/"; then
            connector=$(echo "$file" | sed -n 's|.*/generation/\([^/]*\)\.py|\1|p')
        elif echo "$file" | grep -q "backend/airweave/platform/sources/"; then
            connector=$(echo "$file" | sed -n 's|.*/sources/\([^/]*\)\.py|\1|p')
        elif echo "$file" | grep -q "backend/airweave/platform/entities/"; then
            connector=$(echo "$file" | sed -n 's|.*/entities/\([^/]*\)\.py|\1|p')
        fi

        if [[ -n "$connector" ]] && [[ -f "${MONKE_DIR}/configs/${connector}.yaml" ]]; then
            # Avoid duplicates
            if [[ ${#changed_connectors[@]} -eq 0 ]] || [[ ! " ${changed_connectors[@]} " =~ " ${connector} " ]]; then
                changed_connectors+=("$connector")
            fi
        fi
    done <<< "$changed_files"

    if [[ ${#changed_connectors[@]} -eq 0 ]]; then
        log_info "No testable connector changes detected" >&2
        return 1
    fi

    log_success "Detected changed connectors: ${changed_connectors[*]}" >&2
    echo "${changed_connectors[@]}"
}

# Get hybrid connector list: core + changed
get_hybrid_connectors() {
    # Core connectors that always run
    local core_connectors=("github" "asana" "linear" "google_docs")
    local changed_connectors=()

    # Try to detect changed connectors
    local changed_output
    if changed_output=$(detect_changed_connectors); then
        changed_connectors=($changed_output)
        log_info "Found changed connectors: ${changed_connectors[*]}" >&2
    else
        changed_connectors=()
        log_info "No changed connectors detected" >&2
    fi

    # Combine core + changed, removing duplicates
    local all_connectors=("${core_connectors[@]}")
    if [[ ${#changed_connectors[@]} -gt 0 ]]; then
        for changed in "${changed_connectors[@]}"; do
            # Check if not already in core connectors
            if [[ ! " ${core_connectors[@]} " =~ " ${changed} " ]]; then
                all_connectors+=("$changed")
            fi
        done
    fi

    echo "${all_connectors[@]}"
}

# Ensure minimum number of connectors (pad with extras if needed)
ensure_min_connectors() {
    local connectors=("$@")
    local min_connectors="${MONKE_MIN_CONNECTORS:-4}"

    # If we already have enough, just return them
    if [[ ${#connectors[@]} -ge $min_connectors ]]; then
        echo "${connectors[@]}"
        return 0
    fi

    log_info "Only ${#connectors[@]} connectors, padding to minimum of $min_connectors..." >&2

    # Get all available connectors
    local available=($(get_available_connectors))

    # Add extras until we reach minimum
    for connector in "${available[@]}"; do
        if [[ ${#connectors[@]} -ge $min_connectors ]]; then
            break
        fi

        # Add if not already in list
        if [[ ! " ${connectors[@]} " =~ " ${connector} " ]]; then
            connectors+=("$connector")
            log_info "Added extra connector: $connector" >&2
        fi
    done

    echo "${connectors[@]}"
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
    local env_file="${MONKE_ENV_FILE:-${MONKE_DIR}/.env}"

    if [[ ${#connectors[@]} -eq 0 ]]; then
        log_error "No connectors to test"
        return 1
    fi

    # Check environment file
    if [[ ! -f "$env_file" ]]; then
        log_error "Environment file not found: $env_file"
        log_info "Create monke/.env and add your credentials (or set MONKE_ENV_FILE)"
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

    # Run the unified runner normally
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
    local print_connectors=false

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
            --print-connectors)
                print_connectors=true
                shift
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

    # If --print-connectors, just determine and print them (for CI matrix generation)
    if [[ "$print_connectors" == true ]]; then
        case "$mode" in
            all)
                connectors=($(get_available_connectors))
                ;;
            changed)
                connectors=($(get_hybrid_connectors))
                ;;
            specific)
                if [[ ${#connectors[@]} -eq 0 ]]; then
                    connectors=($(get_hybrid_connectors))
                fi
                ;;
        esac

        # Ensure minimum of 4 connectors for CI parallelism
        connectors=($(ensure_min_connectors "${connectors[@]}" 2>/dev/null))

        # Print space-separated list to stdout (only this, no other output)
        echo "${connectors[@]}"
        exit 0
    fi

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
            log_step "Running hybrid connector tests (core + changed)..."
            connectors=($(get_hybrid_connectors))
            if [[ ${#connectors[@]} -eq 0 ]]; then
                log_error "No connectors available for testing"
                exit 1
            fi
            ;;
        specific)
            if [[ ${#connectors[@]} -eq 0 ]]; then
                # No arguments provided - run hybrid approach
                log_info "No connectors specified, running hybrid connector tests..."
                connectors=($(get_hybrid_connectors))
                if [[ ${#connectors[@]} -eq 0 ]]; then
                    log_error "No connectors available for testing"
                    exit 1
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

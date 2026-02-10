#!/usr/bin/env bash
#
# Airweave Local Development Setup
# Start all services for local development
#

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

SCRIPT_NAME="./$(basename "$0")"
NONINTERACTIVE="${NONINTERACTIVE:-}"
SKIP_LOCAL_EMBEDDINGS="${SKIP_LOCAL_EMBEDDINGS:-}"
SKIP_FRONTEND="${SKIP_FRONTEND:-}"
VERBOSE="${VERBOSE:-}"
QUIET="${QUIET:-}"

# Action flags
ACTION_RESTART=""
ACTION_RECREATE=""
ACTION_DESTROY=""
SKIP_CONTAINER_CREATION=""
SKIP_ENV_SETUP=""
SKIP_HEALTH_CHECKS=""

# =============================================================================
# Colors and Styling
# =============================================================================

# Set defaults (overridden by setup_colors if terminal supports it)
BOLD=''
RESET=''

setup_colors() {
    if [[ -t 1 ]] && [[ -z ${NO_COLOR:-} ]]; then
        BOLD=$'\033[1m'
        RESET=$'\033[0m'
    fi
}

# =============================================================================
# Logging Functions
# =============================================================================

log_info()    { printf "  %s\n" "$1"; }
log_note()    { printf "ℹ️ %s\n" "$1"; }
log_success() { printf "✅ %s\n" "$1"; }
log_error()   { printf "❌ %s\n" "$1" >&2; }
log_warning() { printf "⚠️ %s\n" "$1"; }
log_debug()   { [[ -n $VERBOSE ]] && printf "   [debug] %s\n" "$1" || true; }
log_prompt()  { printf "\n👉 "; }

section() {
    local title=$1
    printf "\n${BOLD}==> %s${RESET}\n" "$title"
}

subsection() {
    local title=$1
    printf "\n${BOLD}%s${RESET}\n\n" "$title"
}

print_banner() {
    [[ -n $QUIET ]] && return

    # Weave logo lines
    local logo=(
        "         ++             "
        "        + .+++-         "
        "    +++++   +++.        "
        "    ++  ++- -   .+      "
        "   +-   ++++- .++.      "
        "     .++    -++++       "
        "      -+++. ++          "
        "          ++-           "
    )

    # Airweave ASCII text
    local text=(
        "    _    _                                 "
        "   / \\  (_)_ ____      _____  __ ___   _____ "
        "  / _ \\ | | '__\\ \\ /\\ / / _ \\/ _\` \\ \\ / / _ \\"
        " / ___ \\| | |   \\ V  V /  __/ (_| |\\ V /  __/"
        "/_/   \\_\\_|_|    \\_/\\_/ \\___|\\__,_| \\_/ \\___|"
    )

    printf "\n"

    if [[ -z $NONINTERACTIVE ]]; then
        # Animated version: draw logo and text together, line by line
        for i in {0..7}; do
            printf "%s" "${logo[$i]}"
            if [[ $i -ge 1 && $i -le 5 ]]; then
                printf "%s" "${text[$((i - 1))]}"
            fi
            printf "\n"
            sleep 0.008
        done

        printf "\n"
        printf "Local Development Setup\n"
        sleep 0.05
        printf "───────────────────────────────────────\n"
    else
        # Static version for CI/non-interactive
        for i in {0..7}; do
            printf "%s" "${logo[$i]}"
            if [[ $i -ge 1 && $i -le 5 ]]; then
                printf "%s" "${text[$((i - 1))]}"
            fi
            printf "\n"
        done
        printf "\nLocal Development Setup\n"
        printf "───────────────────────────────────────\n"
    fi
}

print_success() {
    printf "${BOLD}🎉 All services started successfully!${RESET}\n"
}

# =============================================================================
# Helper Functions
# =============================================================================

have_cmd() { command -v "$1" >/dev/null 2>&1; }

# Run command with timeout (portable across Linux/macOS)
run_with_timeout() {
    local secs=$1; shift
    if have_cmd timeout; then
        timeout "$secs" "$@"
    elif have_cmd gtimeout; then
        gtimeout "$secs" "$@"
    else
        "$@"  # No timeout available, run directly
    fi
}

get_env_value() {
    local key=$1
    # Note: Use || true to prevent pipefail from causing exit when key doesn't exist
    grep "^${key}=" .env 2>/dev/null | head -1 | cut -d'=' -f2- | tr -d '"' | tr -d "'" || true
}

set_env_value() {
    local key=$1 value=$2
    local tmp_file
    tmp_file=$(mktemp) || { log_error "Failed to create temp file"; return 1; }
    grep -v "^${key}=" .env > "$tmp_file" 2>/dev/null || true
    mv "$tmp_file" .env
    printf '%s="%s"\n' "$key" "$value" >> .env
}

ensure_env_value() {
    local key=$1 value=$2
    if ! grep -q "^${key}=" .env 2>/dev/null; then
        printf '%s=%s\n' "$key" "$value" >> .env
        return 0
    fi
    return 1
}

# Wait for a condition with retry count on updating line
wait_for() {
    local description=$1
    local max_attempts=$2
    local check_cmd=$3
    local attempt=0

    while (( attempt < max_attempts )); do
        # eval is safe here - check_cmd is always a function name defined in this script
        if eval "$check_cmd" >/dev/null 2>&1; then
            printf "\r\033[K"
            log_success "$description"
            return 0
        fi
        ((attempt++))

        printf "\r\033[K⏳ %s (%d/%d)..." "$description" "$attempt" "$max_attempts"
        sleep 5
    done

    printf "\r\033[K"
    log_error "$description failed after $max_attempts attempts"
    return 1
}

# Prompt for API key only if not already set
prompt_api_key() {
    local key_name=$1
    local description=$2

    local existing_value
    existing_value=$(get_env_value "$key_name")

    # Skip if key exists and is not a placeholder
    if [[ -n $existing_value && $existing_value != "your-api-key-here" ]]; then
        log_success "$key_name configured"
        return 0
    fi

    # Skip in non-interactive mode
    if [[ -n $NONINTERACTIVE ]]; then
        log_info "$key_name not set (non-interactive mode)"
        return 0
    fi

    printf "\n%s\n" "$description"
    log_prompt
    read -rp "Add $key_name now? (y/n): " response

    if [[ $response =~ ^[Yy]$ ]]; then
        log_prompt
        read -rp "Enter your $key_name: " key_value
        set_env_value "$key_name" "$key_value"
        log_success "$key_name added to .env"
    else
        log_info "You can add $key_name later by editing .env"
    fi
}

# =============================================================================
# Usage
# =============================================================================

usage() {
    cat <<EOF
${BOLD}Usage:${RESET} $SCRIPT_NAME [OPTIONS]

Start Airweave local development environment.

${BOLD}Options:${RESET}
  -h, --help                Show this help message
  -v, --verbose             Show debug output
  -q, --quiet               Minimal output
  --noninteractive          Skip all interactive prompts
  --skip-local-embeddings   Don't start local embeddings service
  --skip-frontend           Don't start frontend UI

${BOLD}Actions:${RESET}
  --restart                 Restart existing containers (preserves data)
  --recreate                Stop, remove, and recreate all containers
  --destroy                 Remove everything: containers, volumes, and data

${BOLD}Environment variables:${RESET}
  NONINTERACTIVE=1          Same as --noninteractive
  SKIP_LOCAL_EMBEDDINGS=1   Same as --skip-local-embeddings
  SKIP_FRONTEND=1           Same as --skip-frontend
  VERBOSE=1                 Same as --verbose
  QUIET=1                   Same as --quiet
  NO_COLOR=1                Disable colored output

${BOLD}Examples:${RESET}
  $SCRIPT_NAME                        # Interactive setup
  $SCRIPT_NAME --noninteractive       # CI/automated setup
  $SCRIPT_NAME --skip-frontend        # Backend only
  $SCRIPT_NAME --restart              # Restart all services
  $SCRIPT_NAME --recreate             # Fresh containers, keep volumes
  $SCRIPT_NAME --destroy              # Complete cleanup
  VERBOSE=1 $SCRIPT_NAME              # Debug mode
EOF
    exit 0
}

# =============================================================================
# Argument Parsing
# =============================================================================

# Set up colors early so --help output is styled
setup_colors

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage ;;
        -v|--verbose) VERBOSE=1; shift ;;
        -q|--quiet) QUIET=1; shift ;;
        --noninteractive) NONINTERACTIVE=1; shift ;;
        --skip-local-embeddings) SKIP_LOCAL_EMBEDDINGS=1; shift ;;
        --skip-frontend) SKIP_FRONTEND=1; shift ;;
        --restart) ACTION_RESTART=1; shift ;;
        --recreate) ACTION_RECREATE=1; shift ;;
        --destroy) ACTION_DESTROY=1; shift ;;
        *)
            log_error "Unknown option: $1"
            echo "Run '$SCRIPT_NAME --help' for usage"
            exit 2
            ;;
    esac
done

# Enable debug mode if verbose
[[ -n $VERBOSE ]] && set -x

# =============================================================================
# Main Script
# =============================================================================

print_banner

# -----------------------------------------------------------------------------
# Detect Container Runtime (do this first to check for existing containers)
# -----------------------------------------------------------------------------

COMPOSE_FILE="docker/docker-compose.yml"

# Find compose command
if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif have_cmd docker-compose; then
    COMPOSE_CMD="docker-compose"
elif have_cmd podman-compose; then
    COMPOSE_CMD="podman-compose"
else
    log_error "Docker Compose not found"
    echo "Please install Docker Compose and try again."
    exit 1
fi

# Find container command
if docker info >/dev/null 2>&1; then
    CONTAINER_CMD="docker"
elif have_cmd podman && podman info >/dev/null 2>&1; then
    CONTAINER_CMD="podman"
else
    log_error "Docker daemon not running"
    echo "Please start Docker and try again."
    exit 1
fi

log_debug "Using: $CONTAINER_CMD + $COMPOSE_CMD"

# -----------------------------------------------------------------------------
# Handle Action Flags (--destroy, --recreate, --restart)
# -----------------------------------------------------------------------------

# Handle --destroy: Remove everything and exit
if [[ -n $ACTION_DESTROY ]]; then
    section "Destroying Airweave"

    # Confirm unless noninteractive
    if [[ -z $NONINTERACTIVE ]]; then
        log_warning "This will remove ALL containers, volumes, and data!"
        log_prompt
        read -rp "Are you sure? (y/n): " response
        if [[ ! $response =~ ^[Yy]$ ]]; then
            log_info "Aborted"
            exit 0
        fi
    fi

    log_info "Stopping and removing containers and volumes..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" down --volumes --remove-orphans 2>/dev/null || true

    log_success "All Airweave resources removed"
    echo ""
    echo "To start fresh: $SCRIPT_NAME"
    exit 0
fi

# Handle --recreate: Remove containers and volumes, then continue with fresh start
if [[ -n $ACTION_RECREATE ]]; then
    log_info "Recreating containers..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" down --volumes --remove-orphans 2>/dev/null || true
    log_success "Old containers and volumes removed"
fi

# Handle --restart: Restart existing containers and skip to health checks
if [[ -n $ACTION_RESTART ]]; then
    # Validate containers exist before attempting restart
    if [[ -z $($COMPOSE_CMD -f "$COMPOSE_FILE" ps -a -q 2>/dev/null) ]]; then
        log_error "No containers to restart. Run '$SCRIPT_NAME' first."
        exit 1
    fi

    log_info "Restarting services..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" restart
    log_success "Services restarted"

    # Skip container creation and env setup, but still do health checks
    SKIP_CONTAINER_CREATION=1
    SKIP_ENV_SETUP=1
fi

# -----------------------------------------------------------------------------
# Check for Existing Containers (before environment setup)
# -----------------------------------------------------------------------------

# Handle existing containers (normal startup without action flags)
if [[ -z $ACTION_RECREATE && -z $ACTION_RESTART && -z $SKIP_CONTAINER_CREATION ]]; then
    # Use compose to detect containers managed by this compose file
    existing_containers=$($COMPOSE_CMD -f "$COMPOSE_FILE" ps -a -q 2>/dev/null)

    if [[ -n $existing_containers ]]; then
        # Check if containers are running
        running_containers=$($COMPOSE_CMD -f "$COMPOSE_FILE" ps -q 2>/dev/null)

        if [[ -n $running_containers ]]; then
            # Containers are already running - just show status
            log_success "Airweave is already running"
            SKIP_CONTAINER_CREATION=1
            SKIP_ENV_SETUP=1
            SKIP_HEALTH_CHECKS=1
        else
            # Containers exist but are stopped - start them
            log_note "Airweave containers found (stopped)"
            log_info "Starting existing containers..."

            # Start the existing containers
            $COMPOSE_CMD -f "$COMPOSE_FILE" up -d
            log_success "Containers started"
            SKIP_CONTAINER_CREATION=1
            SKIP_ENV_SETUP=1
            # Don't skip health checks - we just started them
        fi
    fi
fi

# -----------------------------------------------------------------------------
# Check Environment (only for fresh start)
# -----------------------------------------------------------------------------
if [[ -z $SKIP_ENV_SETUP ]]; then
    section "Checking Environment"

    # Create .env if needed
    if [[ ! -f .env ]]; then
        cp .env.example .env
        log_success "Created .env from .env.example"
    else
        log_success ".env file exists"
    fi

    # Generate ENCRYPTION_KEY if needed
    existing_key=$(get_env_value "ENCRYPTION_KEY")
    if [[ -n $existing_key ]]; then
        log_success "ENCRYPTION_KEY configured"
    else
        new_key=$(openssl rand -base64 32)
        set_env_value "ENCRYPTION_KEY" "$new_key"
        log_success "ENCRYPTION_KEY generated"
    fi

    # Generate STATE_SECRET if needed
    existing_secret=$(get_env_value "STATE_SECRET")
    if [[ -n $existing_secret ]]; then
        log_success "STATE_SECRET configured"
    else
        new_secret=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))' 2>/dev/null || openssl rand -base64 32)
        set_env_value "STATE_SECRET" "$new_secret"
        log_success "STATE_SECRET generated"
    fi

    # Add SKIP_AZURE_STORAGE for faster local startup
    if ensure_env_value "SKIP_AZURE_STORAGE" "true"; then
        log_debug "Added SKIP_AZURE_STORAGE=true"
    fi

    # Prompt for API keys (only if not already set)
    prompt_api_key "OPENAI_API_KEY" "OpenAI API key is required for files and natural language search."
    prompt_api_key "MISTRAL_API_KEY" "Mistral API key is required for certain AI functionality."

    section "Starting Services"
fi

# -----------------------------------------------------------------------------
# Determine Services to Start & Embedding Dimensions
# -----------------------------------------------------------------------------
USE_LOCAL_EMBEDDINGS=true
USE_FRONTEND=true
USE_VESPA=true  # Always enabled

# Detect available API keys
openai_key=$(get_env_value "OPENAI_API_KEY")
mistral_key=$(get_env_value "MISTRAL_API_KEY")

# Only show configuration messages when actually starting services fresh
if [[ -z $SKIP_CONTAINER_CREATION ]]; then
    # Auto-detect OpenAI key to skip local embeddings
    if [[ -n $openai_key && $openai_key != "your-api-key-here" ]]; then
        log_note "OpenAI detected — skipping local embeddings (~2GB)"
        USE_LOCAL_EMBEDDINGS=false
    fi

    # Check explicit skip flags
    if [[ -n $SKIP_LOCAL_EMBEDDINGS ]]; then
        log_note "Skipping local embeddings (flag set)"
        USE_LOCAL_EMBEDDINGS=false
    fi

    # Set EMBEDDING_DIMENSIONS based on available providers (if not already set)
    # Priority: OpenAI (1536) > Mistral (1024) > Local (384)
    current_dim=$(get_env_value "EMBEDDING_DIMENSIONS")
    if [[ -z $current_dim ]]; then
        if [[ -n $openai_key && $openai_key != "your-api-key-here" ]]; then
            set_env_value "EMBEDDING_DIMENSIONS" "1536"
            log_success "EMBEDDING_DIMENSIONS=1536 (OpenAI)"
        elif [[ -n $mistral_key && $mistral_key != "your-api-key-here" ]]; then
            set_env_value "EMBEDDING_DIMENSIONS" "1024"
            log_success "EMBEDDING_DIMENSIONS=1024 (Mistral)"
        elif [[ $USE_LOCAL_EMBEDDINGS == true ]]; then
            set_env_value "EMBEDDING_DIMENSIONS" "384"
            log_success "EMBEDDING_DIMENSIONS=384 (local)"
        else
            log_warning "No embedding provider configured"
        fi
    else
        log_success "EMBEDDING_DIMENSIONS=$current_dim (from .env)"
    fi

    if [[ -n $SKIP_FRONTEND ]]; then
        log_note "Skipping frontend (flag set)"
        USE_FRONTEND=false
    fi
else
    # When reusing existing containers, just set flags based on skip settings
    if [[ -n $openai_key && $openai_key != "your-api-key-here" ]] || [[ -n $SKIP_LOCAL_EMBEDDINGS ]]; then
        USE_LOCAL_EMBEDDINGS=false
    fi
    if [[ -n $SKIP_FRONTEND ]]; then
        USE_FRONTEND=false
    fi
fi

# -----------------------------------------------------------------------------
# Start Services (skip if --restart was used)
# -----------------------------------------------------------------------------
if [[ -z $SKIP_CONTAINER_CREATION ]]; then
    # Build compose command with profiles
    compose_args=(-f docker/docker-compose.yml)
    [[ $USE_LOCAL_EMBEDDINGS == true ]] && compose_args+=(--profile local-embeddings)
    [[ $USE_FRONTEND == true ]] && compose_args+=(--profile frontend)
    [[ $USE_VESPA == true ]] && compose_args+=(--profile vespa)

    if ! $COMPOSE_CMD "${compose_args[@]}" up -d; then
        log_error "Failed to start Docker services"
        echo "Check the error messages above and try running:"
        echo "  docker logs airweave-backend"
        echo "  docker logs airweave-frontend"
        exit 1
    fi
    log_success "Docker services started"
fi

# -----------------------------------------------------------------------------
# Wait for Services (skip if containers were already running)
# -----------------------------------------------------------------------------
if [[ -z $SKIP_HEALTH_CHECKS ]]; then
    section "Waiting for Services"

    # Wait for Vespa
    vespa_check() {
        local init_status init_exit_code doc_status
        init_status=$($CONTAINER_CMD inspect airweave-vespa-init --format='{{.State.Status}}' 2>/dev/null || echo "not_found")
        init_exit_code=$($CONTAINER_CMD inspect airweave-vespa-init --format='{{.State.ExitCode}}' 2>/dev/null || echo "1")

        # Detect permanent failure: init container crashed
        if [[ $init_status == "exited" && $init_exit_code != "0" ]]; then
            printf "\r\033[K"
            log_error "Vespa init failed (exit code: $init_exit_code)"
            log_info "Check logs: $CONTAINER_CMD logs airweave-vespa-init"
            exit 1
        fi

        if [[ $init_status == "exited" && $init_exit_code == "0" ]]; then
            doc_status=$(run_with_timeout 5 curl -s -o /dev/null -w "%{http_code}" http://localhost:8081/document/v1/ 2>/dev/null || echo "000")
            [[ $doc_status != "000" && $doc_status -ge 100 ]] 2>/dev/null
        else
            return 1
        fi
    }

    if ! wait_for "Vespa ready" 60 vespa_check; then
        echo ""
        echo "Vespa troubleshooting:"
        echo "  1. Check Vespa logs: $CONTAINER_CMD logs airweave-vespa"
        echo "  2. Check init logs:  $CONTAINER_CMD logs airweave-vespa-init"
        echo "  3. Check health:     curl http://localhost:8081/state/v1/health"
        exit 1
    fi

    # Wait for backend
    backend_check() {
        $CONTAINER_CMD exec airweave-backend curl -sf http://localhost:8001/health
    }

    if ! wait_for "Backend healthy" 30 backend_check; then
        echo ""
        echo "Backend troubleshooting:"
        echo "  - Check logs: docker logs airweave-backend"
        echo "  - Common issues: database connection, missing env vars"
        exit 1
    fi

    # Start frontend if needed
    if [[ $USE_FRONTEND == true ]]; then
        frontend_status=$($CONTAINER_CMD inspect airweave-frontend --format='{{.State.Status}}' 2>/dev/null || echo "")
        if [[ $frontend_status == "created" || $frontend_status == "exited" ]]; then
            $CONTAINER_CMD start airweave-frontend >/dev/null 2>&1 || true
        fi
    fi
fi

# -----------------------------------------------------------------------------
# Final Status
# -----------------------------------------------------------------------------
section "🚀 Airweave Status"

services_healthy=true

# Check main services
if $CONTAINER_CMD exec airweave-backend curl -sf http://localhost:8001/health >/dev/null 2>&1; then
    log_success "Backend API     http://localhost:8001"
else
    log_error "Backend API     Not responding"
    services_healthy=false
fi

if [[ $USE_FRONTEND == true ]]; then
    if curl -sf http://localhost:8080 >/dev/null 2>&1; then
        log_success "Frontend UI     http://localhost:8080"
    else
        log_error "Frontend UI     Not responding"
        services_healthy=false
    fi
else
    log_info "Frontend UI     Skipped"
fi

subsection "Other services:"

printf "📊 Temporal UI     http://localhost:8088\n"
printf "🗄️ PostgreSQL      localhost:5432\n"
if curl -sf http://localhost:8081/state/v1/health 2>/dev/null | grep -q '"up"'; then
    printf "🔎 Vespa           http://localhost:8081\n"
else
    printf "⚠️  Vespa           Not responding\n"
fi

if [[ $USE_LOCAL_EMBEDDINGS == true ]]; then
    printf "🤖 Embeddings      http://localhost:9878 (local)\n"
else
    printf "🤖 Embeddings      OpenAI API\n"
fi

# Help text (always shown)
echo ""
echo "────────────────────────────────────────────"
echo "To view logs:     docker logs <container-name>"
echo "To stop services: docker compose -f docker/docker-compose.yml down"
echo "To restart:       $SCRIPT_NAME --restart"
echo "To recreate:      $SCRIPT_NAME --recreate"
echo ""

# Final message
if [[ $services_healthy == true ]]; then
    print_success
else
    printf "⚠️  Some services failed to start. Check logs above.\n"
    exit 1
fi

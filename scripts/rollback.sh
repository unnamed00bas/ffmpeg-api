#!/bin/bash

# Rollback script for FFmpeg API
# This script handles rollback to the previous version

set -e  # Exit on any error
set -u  # Exit on undefined variables

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/rollback_$(date +%Y%m%d_%H%M%S).log"
BACKUP_DIR="${PROJECT_DIR}/backups"
ENV_FILE="${PROJECT_DIR}/.env"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Logging function
log() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} [${level}] ${message}" | tee -a "$LOG_FILE"
}

log_info() {
    log "INFO" "${GREEN}$@${NC}"
}

log_warn() {
    log "WARN" "${YELLOW}$@${NC}"
}

log_error() {
    log "ERROR" "${RED}$@${NC}"
}

log_debug() {
    log "DEBUG" "${BLUE}$@${NC}"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local missing=0
    
    if ! command_exists docker; then
        log_error "Docker is not installed"
        missing=1
    fi
    
    if ! command_exists docker-compose; then
        log_error "Docker Compose is not installed"
        missing=1
    fi
    
    if ! command_exists git; then
        log_error "Git is not installed"
        missing=1
    fi
    
    if [ $missing -eq 1 ]; then
        log_error "Missing required tools. Please install them before continuing."
        exit 1
    fi
    
    log_info "All prerequisites are satisfied."
}

# Function to load environment variables
load_env() {
    log_info "Loading environment variables..."
    
    if [ -f "$ENV_FILE" ]; then
        set -a
        source "$ENV_FILE"
        set +a
        log_info "Environment variables loaded successfully."
    else
        log_warn "Environment file not found: $ENV_FILE"
    fi
}

# Function to get previous commit
get_previous_commit() {
    log_info "Getting previous commit..."
    
    cd "$PROJECT_DIR"
    
    if [ ! -d ".git" ]; then
        log_error "Not a git repository."
        exit 1
    fi
    
    local current_commit=$(git rev-parse HEAD)
    local previous_commit=$(git rev-parse HEAD^1)
    
    if [ -z "$previous_commit" ] || [ "$previous_commit" == "$current_commit" ]; then
        log_error "No previous commit found. This is likely the initial commit."
        exit 1
    fi
    
    echo "$previous_commit"
}

# Function to show commit info
show_commit_info() {
    local commit_hash=$1
    
    log_info "Commit Information:"
    git log -1 --oneline --decorate "$commit_hash"
    git log -1 --format="Author: %an <%ae>" "$commit_hash"
    git log -1 --format="Date: %ad" "$commit_hash"
    git log -1 --format="%s" "$commit_hash"
}

# Function to backup current version before rollback
backup_current() {
    log_info "Backing up current version..."
    
    local backup_name="rollback_backup_$(date +%Y%m%d_%H%M%S)"
    local backup_path="${BACKUP_DIR}/${backup_name}"
    
    mkdir -p "$backup_path"
    
    # Copy environment file
    if [ -f "$ENV_FILE" ]; then
        cp "$ENV_FILE" "${backup_path}/.env"
    fi
    
    # Save current commit
    cd "$PROJECT_DIR"
    git rev-parse HEAD > "${backup_path}/current_commit.txt"
    
    # Copy docker-compose files
    cp docker-compose*.yml "$backup_path/" 2>/dev/null || true
    
    log_info "Current version backed up to: ${backup_path}"
}

# Function to checkout previous version
checkout_previous() {
    local previous_commit=$1
    
    log_info "Checking out previous version: ${previous_commit}"
    
    cd "$PROJECT_DIR"
    
    # Checkout previous commit
    git checkout "$previous_commit"
    
    log_info "Checked out to previous version."
}

# Function to restore from backup if git rollback fails
restore_from_backup() {
    log_info "Attempting to restore from latest backup..."
    
    # Find latest backup
    local latest_backup=$(find "$BACKUP_DIR" -maxdepth 1 -type d -name "pre-deploy_*" | sort -r | head -1)
    
    if [ -z "$latest_backup" ]; then
        log_error "No backup found."
        return 1
    fi
    
    log_info "Found backup: ${latest_backup}"
    
    # Restore from backup
    if [ -f "${SCRIPT_DIR}/restore.sh" ]; then
        bash "${SCRIPT_DIR}/restore.sh" "$(basename "$latest_backup")"
    else
        log_error "Restore script not found."
        return 1
    fi
}

# Function to rebuild and redeploy
rebuild_and_redeploy() {
    log_info "Rebuilding and redeploying..."
    
    cd "$PROJECT_DIR"
    
    # Stop containers
    log_info "Stopping containers..."
    docker-compose stop --timeout 60
    
    # Rebuild images
    log_info "Rebuilding Docker images..."
    docker-compose build --no-cache
    
    # Start containers
    log_info "Starting containers..."
    docker-compose up -d
    
    log_info "Containers rebuilt and restarted."
}

# Function to run database migrations rollback
rollback_migrations() {
    log_info "Rolling back database migrations..."
    
    cd "$PROJECT_DIR"
    
    # Start database temporarily
    docker-compose up -d postgres
    
    # Wait for database to be ready
    log_info "Waiting for database to be ready..."
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if docker-compose exec -T postgres pg_isready -U "${POSTGRES_USER:-postgres_user}" >/dev/null 2>&1; then
            log_info "Database is ready."
            break
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    if [ $attempt -eq $max_attempts ]; then
        log_warn "Database failed to become ready. Skipping migration rollback."
        return 1
    fi
    
    # Rollback migrations by one step
    docker-compose run --rm api alembic downgrade -1
    
    log_info "Database migrations rolled back successfully."
}

# Function to health check
health_check() {
    log_info "Performing health check after rollback..."
    
    cd "$PROJECT_DIR"
    
    local max_attempts=30
    local attempt=0
    local health_check_url="${HEALTH_CHECK_URL:-http://localhost:8000/api/v1/health}"
    
    log_info "Checking health at: ${health_check_url}"
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -f -s "${health_check_url}" >/dev/null 2>&1; then
            log_info "Health check passed!"
            return 0
        fi
        
        attempt=$((attempt + 1))
        log_debug "Health check attempt ${attempt}/${max_attempts} failed. Retrying..."
        sleep 3
    done
    
    log_error "Health check failed after ${max_attempts} attempts."
    
    # Show container logs for debugging
    log_info "Container logs:"
    docker-compose logs --tail=50
    
    return 1
}

# Function to show rollback summary
show_summary() {
    log_info "Rollback Summary"
    log_info "================"
    
    cd "$PROJECT_DIR"
    
    local current_commit=$(git rev-parse --short HEAD)
    
    log_info "Current commit: ${current_commit}"
    
    log_info "Running containers:"
    docker-compose ps
    
    log_info "Rollback completed successfully!"
}

# Function to create rollback point
create_rollback_point() {
    log_info "Creating rollback point..."
    
    local tag_name="rollback_point_$(date +%Y%m%d_%H%M%S)"
    
    cd "$PROJECT_DIR"
    
    git tag "$tag_name"
    
    log_info "Rollback point created: ${tag_name}"
}

# Function to rollback to specific tag
rollback_to_tag() {
    local tag_name=$1
    
    log_info "Rolling back to tag: ${tag_name}"
    
    cd "$PROJECT_DIR"
    
    # Check if tag exists
    if ! git rev-parse "$tag_name" >/dev/null 2>&1; then
        log_error "Tag not found: ${tag_name}"
        exit 1
    fi
    
    # Checkout tag
    git checkout "$tag_name"
    
    log_info "Checked out to tag: ${tag_name}"
}

# Main rollback function
main() {
    log_info "Starting rollback process..."
    log_info "Log file: ${LOG_FILE}"
    
    # Parse command line arguments
    SKIP_HEALTH_CHECK=${SKIP_HEALTH_CHECK:-false}
    ROLLBACK_TO=""
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-health-check)
                SKIP_HEALTH_CHECK=true
                shift
                ;;
            --to-tag)
                ROLLBACK_TO="$2"
                shift 2
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --skip-health-check    Skip health check after rollback"
                echo "  --to-tag TAG           Rollback to specific tag"
                echo "  --help                 Show this help message"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Execute rollback steps
    check_prerequisites
    load_env
    backup_current
    
    if [ -n "$ROLLBACK_TO" ]; then
        rollback_to_tag "$ROLLBACK_TO"
    else
        local previous_commit=$(get_previous_commit)
        show_commit_info "$previous_commit"
        checkout_previous "$previous_commit"
    fi
    
    rebuild_and_redeploy
    rollback_migrations || true  # Don't fail if migration rollback fails
    
    if [ "$SKIP_HEALTH_CHECK" != "true" ]; then
        if ! health_check; then
            log_error "Health check failed after rollback."
            log_error "Application may be in an inconsistent state."
            log_info "Please investigate and manually fix if necessary."
            exit 1
        fi
    fi
    
    show_summary
    
    log_info "Rollback completed successfully!"
}

# Trap errors
trap 'log_error "Rollback failed at line $LINENO"' ERR

# Run main function
main "$@"

#!/bin/bash

# Deployment script for FFmpeg API
# This script handles deployment of the application to production

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
LOG_FILE="${LOG_DIR}/deploy_$(date +%Y%m%d_%H%M%S).log"
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
    
    if [ ! -f "$ENV_FILE" ]; then
        log_error "Environment file not found: $ENV_FILE"
        exit 1
    fi
    
    set -a
    source "$ENV_FILE"
    set +a
    
    log_info "Environment variables loaded successfully."
}

# Function to backup before deployment
pre_deploy_backup() {
    log_info "Creating pre-deployment backup..."
    
    if [ -f "${SCRIPT_DIR}/backup.sh" ]; then
        bash "${SCRIPT_DIR}/backup.sh" "pre-deploy"
        log_info "Pre-deployment backup completed."
    else
        log_warn "Backup script not found. Skipping backup."
    fi
}

# Function to pull latest code
pull_code() {
    log_info "Pulling latest code from repository..."
    
    cd "$PROJECT_DIR"
    
    # Check if we're in a git repository
    if [ ! -d ".git" ]; then
        log_error "Not a git repository. Skipping git pull."
        return
    fi
    
    # Stash any local changes
    if [ -n "$(git status --porcelain)" ]; then
        log_warn "Uncommitted changes detected. Stashing them..."
        git stash push -m "Auto-stash before deployment $(date)"
    fi
    
    # Fetch and pull
    git fetch origin
    local current_branch=$(git rev-parse --abbrev-ref HEAD)
    git pull origin "$current_branch"
    
    local commit_hash=$(git rev-parse --short HEAD)
    log_info "Pulled latest code. Commit: ${commit_hash}"
}

# Function to build Docker images
build_images() {
    log_info "Building Docker images..."
    
    cd "$PROJECT_DIR"
    
    # Pull latest images first
    log_info "Pulling latest base images..."
    docker-compose pull || true
    
    # Build images
    log_info "Building application images..."
    docker-compose build --no-cache
    
    log_info "Docker images built successfully."
}

# Function to stop old containers
stop_containers() {
    log_info "Stopping old containers..."
    
    cd "$PROJECT_DIR"
    
    # Graceful shutdown
    docker-compose stop --timeout 60
    
    log_info "Containers stopped successfully."
}

# Function to run database migrations
run_migrations() {
    log_info "Running database migrations..."
    
    cd "$PROJECT_DIR"
    
    # Start only the database temporarily
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
        log_error "Database failed to become ready."
        exit 1
    fi
    
    # Run migrations
    docker-compose run --rm api alembic upgrade head
    
    log_info "Database migrations completed successfully."
}

# Function to start new containers
start_containers() {
    log_info "Starting new containers..."
    
    cd "$PROJECT_DIR"
    
    # Start all services
    docker-compose up -d
    
    log_info "Containers started successfully."
}

# Function to health check
health_check() {
    log_info "Performing health check..."
    
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

# Function to cleanup old images
cleanup() {
    log_info "Cleaning up old Docker images..."
    
    # Remove dangling images
    docker image prune -f
    
    # Remove old images (older than 7 days)
    docker image prune -a -f --filter "until=168h"
    
    log_info "Cleanup completed."
}

# Function to show deployment summary
show_summary() {
    log_info "Deployment Summary"
    log_info "=================="
    
    cd "$PROJECT_DIR"
    
    log_info "Running containers:"
    docker-compose ps
    
    log_info "Docker images:"
    docker images | grep ffmpeg
    
    log_info "Deployment completed successfully!"
}

# Function to rollback on failure
rollback_on_failure() {
    log_error "Deployment failed. Initiating rollback..."
    
    if [ -f "${SCRIPT_DIR}/rollback.sh" ]; then
        bash "${SCRIPT_DIR}/rollback.sh"
    else
        log_error "Rollback script not found. Manual intervention required."
    fi
}

# Main deployment function
main() {
    log_info "Starting deployment process..."
    log_info "Log file: ${LOG_FILE}"
    
    # Parse command line arguments
    SKIP_BACKUP=${SKIP_BACKUP:-false}
    SKIP_HEALTH_CHECK=${SKIP_HEALTH_CHECK:-false}
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-backup)
                SKIP_BACKUP=true
                shift
                ;;
            --skip-health-check)
                SKIP_HEALTH_CHECK=true
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Execute deployment steps
    check_prerequisites
    load_env
    
    if [ "$SKIP_BACKUP" != "true" ]; then
        pre_deploy_backup
    fi
    
    pull_code
    build_images
    stop_containers
    run_migrations
    start_containers
    
    if [ "$SKIP_HEALTH_CHECK" != "true" ]; then
        if ! health_check; then
            log_error "Health check failed."
            rollback_on_failure
            exit 1
        fi
    fi
    
    cleanup
    show_summary
    
    log_info "Deployment completed successfully!"
}

# Trap errors
trap 'log_error "Deployment failed at line $LINENO"' ERR

# Run main function
main "$@"

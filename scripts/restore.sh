#!/bin/bash

# Restore script for FFmpeg API
# This script handles restore of PostgreSQL, MinIO, and configuration from backup

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
LOG_FILE="${LOG_DIR}/restore_$(date +%Y%m%d_%H%M%S).log"
BACKUP_DIR="${PROJECT_DIR}/backups"
ENV_FILE="${PROJECT_DIR}/.env"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Default values
BACKUP_NAME=""
EXTRACT_DIR=""

# Logging function
log() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S'
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
    
    if ! command_exists gzip; then
        log_error "gzip is not installed"
        missing=1
    fi
    
    if ! command_exists tar; then
        log_error "tar is not installed"
        missing=1
    fi
    
    if [ $missing -eq 1 ]; then
        log_error "Missing required tools. Please install them before continuing."
        exit 1
    fi
    
    log_info "All prerequisites are satisfied."
}

# Function to find backup
find_backup() {
    if [ -z "$BACKUP_NAME" ]; then
        # Find the latest backup
        BACKUP_NAME=$(ls -1t "${BACKUP_DIR}"/*.tar.gz 2>/dev/null | head -1)
        
        if [ -z "$BACKUP_NAME" ]; then
            log_error "No backups found in ${BACKUP_DIR}"
            exit 1
        fi
        
        log_info "Using latest backup: $(basename "$BACKUP_NAME")"
    else
        # Check if backup exists
        if [ -f "${BACKUP_DIR}/${BACKUP_NAME}" ]; then
            BACKUP_NAME="${BACKUP_DIR}/${BACKUP_NAME}"
        elif [ -f "$BACKUP_NAME" ]; then
            # Full path provided
            BACKUP_NAME="$BACKUP_NAME"
        else
            log_error "Backup not found: ${BACKUP_NAME}"
            exit 1
        fi
    fi
    
    # Verify backup file
    if [ ! -f "$BACKUP_NAME" ]; then
        log_error "Backup file not found: ${BACKUP_NAME}"
        exit 1
    fi
}

# Function to verify backup integrity
verify_backup() {
    log_info "Verifying backup integrity..."
    
    if ! tar -tzf "$BACKUP_NAME" >/dev/null 2>&1; then
        log_error "Backup archive is corrupted or invalid."
        exit 1
    fi
    
    log_info "Backup integrity verified."
}

# Function to extract backup
extract_backup() {
    log_info "Extracting backup..."
    
    EXTRACT_DIR="${BACKUP_DIR}/restore_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$EXTRACT_DIR"
    
    tar -xzf "$BACKUP_NAME" -C "$EXTRACT_DIR"
    
    # Find the extracted directory
    EXTRACT_DIR="${EXTRACT_DIR}/$(ls -1 "$EXTRACT_DIR" | head -1)"
    
    log_info "Backup extracted to: ${EXTRACT_DIR}"
}

# Function to restore PostgreSQL
restore_postgres() {
    log_info "Starting PostgreSQL restore..."
    
    cd "$PROJECT_DIR"
    
    # Find PostgreSQL backup file
    local postgres_backup=$(find "$EXTRACT_DIR/postgres" -name "postgres_backup_*.sql.gz" | head -1)
    
    if [ -z "$postgres_backup" ]; then
        log_error "PostgreSQL backup file not found."
        return 1
    fi
    
    log_info "Found PostgreSQL backup: $(basename "$postgres_backup")"
    
    # Get PostgreSQL container name
    local postgres_container=$(docker-compose ps -q postgres)
    
    if [ -z "$postgres_container" ]; then
        log_error "PostgreSQL container not found."
        return 1
    fi
    
    local postgres_user="${POSTGRES_USER:-postgres_user}"
    local postgres_db="${POSTGRES_DB:-ffmpeg_api}"
    
    # Decompress backup
    local decompressed_backup="${postgres_backup%.gz}"
    gunzip -c "$postgres_backup" > "$decompressed_backup"
    
    # Confirm restore
    log_warn "This will overwrite the current database!"
    log_warn "Database: ${postgres_db}"
    log_warn "Backup: $(basename "$postgres_backup")"
    
    read -p "Are you sure you want to continue? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        log_info "PostgreSQL restore cancelled by user."
        return 0
    fi
    
    # Start PostgreSQL container
    docker-compose up -d postgres
    
    # Wait for PostgreSQL to be ready
    log_info "Waiting for PostgreSQL to be ready..."
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if docker-compose exec -T postgres pg_isready -U "$postgres_user" >/dev/null 2>&1; then
            log_info "PostgreSQL is ready."
            break
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    if [ $attempt -eq $max_attempts ]; then
        log_error "PostgreSQL failed to become ready."
        rm -f "$decompressed_backup"
        return 1
    fi
    
    # Drop existing database (excluding template databases)
    log_info "Dropping existing database..."
    docker-compose exec -T postgres psql -U "$postgres_user" -d postgres \
        -c "DROP DATABASE IF EXISTS ${postgres_db};" || true
    
    # Create fresh database
    log_info "Creating fresh database..."
    docker-compose exec -T postgres psql -U "$postgres_user" -d postgres \
        -c "CREATE DATABASE ${postgres_db};" || true
    
    # Restore database
    log_info "Restoring database..."
    docker-compose exec -T postgres psql -U "$postgres_user" -d "$postgres_db" < "$decompressed_backup"
    
    if [ $? -eq 0 ]; then
        log_info "PostgreSQL restore completed successfully."
    else
        log_error "PostgreSQL restore failed."
        rm -f "$decompressed_backup"
        return 1
    fi
    
    # Cleanup
    rm -f "$decompressed_backup"
    
    return 0
}

# Function to restore MinIO
restore_minio() {
    log_info "Starting MinIO restore..."
    
    cd "$PROJECT_DIR"
    
    # Find MinIO backup
    local minio_backup=$(find "$EXTRACT_DIR/minio" -name "minio_data_*.tar.gz" | head -1)
    
    if [ -z "$minio_backup" ]; then
        log_warn "MinIO backup file not found. Skipping MinIO restore."
        return 1
    fi
    
    log_info "Found MinIO backup: $(basename "$minio_backup")"
    
    # Get MinIO container name
    local minio_container=$(docker-compose ps -q minio)
    
    if [ -z "$minio_container" ]; then
        log_warn "MinIO container not found. Skipping MinIO restore."
        return 1
    fi
    
    # Get the MinIO data volume
    local minio_volume=$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}' "$minio_container")
    
    if [ -z "$minio_volume" ]; then
        log_warn "Could not find MinIO data volume. Skipping MinIO restore."
        return 1
    fi
    
    # Confirm restore
    log_warn "This will overwrite all MinIO data!"
    log_warn "Volume: ${minio_volume}"
    log_warn "Backup: $(basename "$minio_backup")"
    
    read -p "Are you sure you want to continue? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        log_info "MinIO restore cancelled by user."
        return 0
    fi
    
    # Stop MinIO container
    docker-compose stop minio
    
    # Create a temporary container to restore the volume
    local temp_container="minio-restore-$(date +%s)"
    
    # Clear existing volume data
    docker run --rm \
        -v "${minio_volume}:/data" \
        alpine:latest \
        sh -c "rm -rf /data/* /data/..?* /data/.[!.]*"
    
    # Restore data to volume
    docker run --rm \
        -v "${minio_volume}:/data" \
        -v "$(dirname "$minio_backup"):/backup" \
        alpine:latest \
        tar -xzf "/backup/$(basename "$minio_backup")" -C /data
    
    if [ $? -eq 0 ]; then
        log_info "MinIO restore completed successfully."
    else
        log_error "MinIO restore failed."
        return 1
    fi
    
    # Start MinIO container
    docker-compose start minio
    
    # Wait for MinIO to be ready
    log_info "Waiting for MinIO to be ready..."
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if docker-compose exec -T minio curl -f -s http://localhost:9000/minio/health/live >/dev/null 2>&1; then
            log_info "MinIO is ready."
            break
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    if [ $attempt -eq $max_attempts ]; then
        log_warn "MinIO failed to become ready, but restore was completed."
    fi
    
    return 0
}

# Function to restore configuration
restore_config() {
    log_info "Starting configuration restore..."
    
    # Restore environment file
    if [ -f "${EXTRACT_DIR}/config/.env" ]; then
        log_warn "This will overwrite the current .env file!"
        read -p "Do you want to restore .env file? (yes/no): " confirm
        
        if [ "$confirm" == "yes" ]; then
            cp "${EXTRACT_DIR}/config/.env" "${ENV_FILE}"
            log_info "Environment file restored."
        else
            log_info "Environment file restore skipped."
        fi
    else
        log_warn "Environment file not found in backup."
    fi
    
    # Restore docker-compose files
    if [ -f "${EXTRACT_DIR}/config/docker-compose.yml" ]; then
        log_warn "This will overwrite docker-compose files!"
        read -p "Do you want to restore docker-compose files? (yes/no): " confirm
        
        if [ "$confirm" == "yes" ]; then
            cp "${EXTRACT_DIR}/config/docker-compose"*.yml "${PROJECT_DIR}/"
            log_info "Docker Compose files restored."
        else
            log_info "Docker Compose files restore skipped."
        fi
    fi
    
    # Restore Alembic configuration
    if [ -f "${EXTRACT_DIR}/config/alembic.ini" ]; then
        cp "${EXTRACT_DIR}/config/alembic.ini" "${PROJECT_DIR}/"
        log_info "Alembic configuration restored."
    fi
    
    # Restore Prometheus configuration
    if [ -d "${EXTRACT_DIR}/config/prometheus" ]; then
        cp -r "${EXTRACT_DIR}/config/prometheus"/* "${PROJECT_DIR}/docker/prometheus/"
        log_info "Prometheus configuration restored."
    fi
    
    # Restore Grafana configuration
    if [ -d "${EXTRACT_DIR}/config/grafana" ]; then
        cp -r "${EXTRACT_DIR}/config/grafana"/* "${PROJECT_DIR}/docker/grafana/"
        log_info "Grafana configuration restored."
    fi
    
    log_info "Configuration restore completed successfully."
}

# Function to restore Git state (optional)
restore_git_state() {
    log_info "Checking Git state..."
    
    if [ -f "${EXTRACT_DIR}/config/current_commit.txt" ]; then
        local backup_commit=$(cat "${EXTRACT_DIR}/config/current_commit.txt")
        local current_commit=$(git rev-parse HEAD 2>/dev/null || echo "not-a-git-repo")
        
        log_info "Backup commit: ${backup_commit}"
        log_info "Current commit: ${current_commit}"
        
        if [ "$backup_commit" != "$current_commit" ]; then
            log_warn "Git commit does not match backup."
            log_warn "You may need to checkout the backup commit: git checkout ${backup_commit}"
            read -p "Do you want to checkout the backup commit? (yes/no): " confirm
            
            if [ "$confirm" == "yes" ]; then
                cd "$PROJECT_DIR"
                git checkout "$backup_commit"
                log_info "Checked out to backup commit."
            else
                log_info "Git state restore skipped."
            fi
        else
            log_info "Git commit matches backup."
        fi
    fi
}

# Function to start services
start_services() {
    log_info "Starting services..."
    
    cd "$PROJECT_DIR"
    
    # Stop all services first
    docker-compose down
    
    # Start all services
    docker-compose up -d
    
    log_info "Services started successfully."
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
    return 1
}

# Function to show restore summary
show_summary() {
    log_info "Restore Summary"
    log_info "==============="
    log_info "Backup used: ${BACKUP_NAME}"
    log_info "Extracted to: ${EXTRACT_DIR}"
    log_info "Restore completed successfully!"
    
    # Show container status
    log_info "Container status:"
    docker-compose ps
}

# Main restore function
main() {
    log_info "Starting restore process..."
    log_info "Log file: ${LOG_FILE}"
    
    # Parse command line arguments
    SKIP_POSTGRES=${SKIP_POSTGRES:-false}
    SKIP_MINIO=${SKIP_MINIO:-false}
    SKIP_CONFIG=${SKIP_CONFIG:-false}
    SKIP_SERVICES_START=${SKIP_SERVICES_START:-false}
    SKIP_HEALTH_CHECK=${SKIP_HEALTH_CHECK:-false}
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --backup)
                BACKUP_NAME="$2"
                shift 2
                ;;
            --skip-postgres)
                SKIP_POSTGRES=true
                shift
                ;;
            --skip-minio)
                SKIP_MINIO=true
                shift
                ;;
            --skip-config)
                SKIP_CONFIG=true
                shift
                ;;
            --skip-services-start)
                SKIP_SERVICES_START=true
                shift
                ;;
            --skip-health-check)
                SKIP_HEALTH_CHECK=true
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS] [BACKUP_NAME]"
                echo ""
                echo "Arguments:"
                echo "  BACKUP_NAME           Name or path of backup file (optional, uses latest if not specified)"
                echo ""
                echo "Options:"
                echo "  --backup NAME         Specify backup name or path"
                echo "  --skip-postgres       Skip PostgreSQL restore"
                echo "  --skip-minio          Skip MinIO restore"
                echo "  --skip-config         Skip configuration restore"
                echo "  --skip-services-start Skip starting services after restore"
                echo "  --skip-health-check   Skip health check after restore"
                echo "  --help                Show this help message"
                exit 0
                ;;
            *)
                # Assume it's a backup name
                BACKUP_NAME="$1"
                shift
                ;;
        esac
    done
    
    # Execute restore steps
    check_prerequisites
    find_backup
    verify_backup
    extract_backup
    
    if [ "$SKIP_POSTGRES" != "true" ]; then
        restore_postgres || log_warn "PostgreSQL restore failed or was skipped."
    fi
    
    if [ "$SKIP_MINIO" != "true" ]; then
        restore_minio || log_warn "MinIO restore failed or was skipped."
    fi
    
    if [ "$SKIP_CONFIG" != "true" ]; then
        restore_config
    fi
    
    restore_git_state
    
    if [ "$SKIP_SERVICES_START" != "true" ]; then
        start_services
    fi
    
    if [ "$SKIP_HEALTH_CHECK" != "true" ]; then
        if ! health_check; then
            log_error "Health check failed after restore."
            log_error "Please check the logs and manually investigate."
            exit 1
        fi
    fi
    
    show_summary
    
    log_info "Restore process completed successfully!"
}

# Trap errors
trap 'log_error "Restore failed at line $LINENO"' ERR

# Run main function
main "$@"

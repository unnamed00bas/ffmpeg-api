#!/bin/bash

# Backup script for FFmpeg API
# This script handles backup of PostgreSQL, MinIO, and configuration

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
LOG_FILE="${LOG_DIR}/backup_$(date +%Y%m%d_%H%M%S).log"
BACKUP_DIR="${PROJECT_DIR}/backups"
ENV_FILE="${PROJECT_DIR}/.env"

# Create log and backup directories if they don't exist
mkdir -p "$LOG_DIR"
mkdir -p "$BACKUP_DIR"

# Default values
KEEP_BACKUPS=30
BACKUP_NAME=""
BACKUP_TYPE="manual"

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
    
    if ! command_exists gzip; then
        log_error "gzip is not installed"
        missing=1
    fi
    
    if ! command_exists mc 2>/dev/null; then
        log_warn "MinIO client (mc) is not installed. MinIO backup may be limited."
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
        log_warn "Using default values for database and storage connections."
    fi
}

# Function to create backup directory
create_backup_dir() {
    if [ -z "$BACKUP_NAME" ]; then
        BACKUP_NAME="${BACKUP_TYPE}_$(date +%Y%m%d_%H%M%S)"
    fi
    
    BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"
    
    if [ -d "$BACKUP_PATH" ]; then
        log_error "Backup directory already exists: ${BACKUP_PATH}"
        exit 1
    fi
    
    mkdir -p "$BACKUP_PATH"
    mkdir -p "${BACKUP_PATH}/postgres"
    mkdir -p "${BACKUP_PATH}/minio"
    mkdir -p "${BACKUP_PATH}/config"
    
    log_info "Backup directory created: ${BACKUP_PATH}"
}

# Function to backup PostgreSQL
backup_postgres() {
    log_info "Starting PostgreSQL backup..."
    
    cd "$PROJECT_DIR"
    
    # Get PostgreSQL container name
    local postgres_container=$(docker-compose ps -q postgres)
    
    if [ -z "$postgres_container" ]; then
        log_error "PostgreSQL container not found."
        return 1
    fi
    
    local postgres_user="${POSTGRES_USER:-postgres_user}"
    local postgres_db="${POSTGRES_DB:-ffmpeg_api}"
    local backup_file="${BACKUP_PATH}/postgres/postgres_backup_$(date +%Y%m%d_%H%M%S).sql"
    
    # Start PostgreSQL container if not running
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
        return 1
    fi
    
    # Perform database dump
    log_info "Creating database dump..."
    docker-compose exec -T postgres pg_dump -U "$postgres_user" \
        --clean \
        --if-exists \
        --format=plain \
        --no-owner \
        --no-acl \
        "$postgres_db" > "$backup_file"
    
    if [ $? -eq 0 ]; then
        local backup_size=$(du -h "$backup_file" | cut -f1)
        log_info "PostgreSQL backup completed successfully."
        log_info "Backup size: ${backup_size}"
    else
        log_error "PostgreSQL backup failed."
        return 1
    fi
    
    # Compress the backup
    log_info "Compressing PostgreSQL backup..."
    gzip "$backup_file"
    
    if [ $? -eq 0 ]; then
        local compressed_size=$(du -h "${backup_file}.gz" | cut -f1)
        log_info "Compressed backup size: ${compressed_size}"
    fi
    
    return 0
}

# Function to backup MinIO
backup_minio() {
    log_info "Starting MinIO backup..."
    
    cd "$PROJECT_DIR"
    
    # Get MinIO container name
    local minio_container=$(docker-compose ps -q minio)
    
    if [ -z "$minio_container" ]; then
        log_warn "MinIO container not found. Skipping MinIO backup."
        return 1
    fi
    
    local minio_user="${MINIO_ROOT_USER:-minioadmin}"
    local minio_password="${MINIO_ROOT_PASSWORD:-minioadmin}"
    local minio_bucket="${MINIO_BUCKET_NAME:-ffmpeg-files}"
    local minio_endpoint="${MINIO_ENDPOINT:-localhost:9000}"
    
    # Backup MinIO data directory using Docker volume
    log_info "Backing up MinIO data directory..."
    
    # Get the MinIO data volume
    local minio_volume=$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}' "$minio_container")
    
    if [ -n "$minio_volume" ]; then
        # Create a temporary container to backup the volume
        local temp_container="minio-backup-$(date +%s)"
        
        docker run --rm \
            -v "${minio_volume}:/data:ro" \
            -v "${BACKUP_PATH}/minio:/backup" \
            alpine:latest \
            tar -czf "/backup/minio_data_$(date +%Y%m%d_%H%M%S).tar.gz" -C /data .
        
        if [ $? -eq 0 ]; then
            local backup_size=$(du -h "${BACKUP_PATH}/minio/minio_data_"*.tar.gz | cut -f1)
            log_info "MinIO backup completed successfully."
            log_info "Backup size: ${backup_size}"
        else
            log_error "MinIO backup failed."
            return 1
        fi
    else
        log_warn "Could not find MinIO data volume. Skipping MinIO backup."
    fi
    
    # Alternative: Use MinIO client if available
    if command_exists mc; then
        log_info "Attempting MinIO backup using mc client..."
        
        # Configure MinIO client
        local alias_name="minio-backup"
        mc alias set "$alias_name" "http://${minio_endpoint}" "$minio_user" "$minio_password" 2>/dev/null || true
        
        # Mirror bucket to backup directory
        mc mirror "${alias_name}/${minio_bucket}" "${BACKUP_PATH}/minio/bucket_backup/" 2>/dev/null || true
        
        if [ $? -eq 0 ]; then
            log_info "MinIO bucket backup completed using mc client."
        fi
    fi
    
    return 0
}

# Function to backup configuration
backup_config() {
    log_info "Starting configuration backup..."
    
    # Backup environment file
    if [ -f "$ENV_FILE" ]; then
        cp "$ENV_FILE" "${BACKUP_PATH}/config/.env"
        log_info "Environment file backed up."
    else
        log_warn "Environment file not found: $ENV_FILE"
    fi
    
    # Backup docker-compose files
    cp docker-compose*.yml "${BACKUP_PATH}/config/" 2>/dev/null || true
    log_info "Docker Compose files backed up."
    
    # Backup Alembic configuration
    if [ -f "${PROJECT_DIR}/alembic.ini" ]; then
        cp "${PROJECT_DIR}/alembic.ini" "${BACKUP_PATH}/config/"
        log_info "Alembic configuration backed up."
    fi
    
    # Backup Prometheus configuration
    if [ -d "${PROJECT_DIR}/docker/prometheus" ]; then
        cp -r "${PROJECT_DIR}/docker/prometheus" "${BACKUP_PATH}/config/"
        log_info "Prometheus configuration backed up."
    fi
    
    # Backup Grafana configuration
    if [ -d "${PROJECT_DIR}/docker/grafana" ]; then
        cp -r "${PROJECT_DIR}/docker/grafana" "${BACKUP_PATH}/config/"
        log_info "Grafana configuration backed up."
    fi
    
    # Backup current Git state
    if [ -d "${PROJECT_DIR}/.git" ]; then
        cd "$PROJECT_DIR"
        git rev-parse HEAD > "${BACKUP_PATH}/config/current_commit.txt"
        git rev-parse --abbrev-ref HEAD > "${BACKUP_PATH}/config/current_branch.txt"
        git log -1 --format="%H|%an|%ae|%ad|%s" > "${BACKUP_PATH}/config/latest_commit.txt"
        log_info "Git state backed up."
    fi
    
    log_info "Configuration backup completed successfully."
}

# Function to compress backup
compress_backup() {
    log_info "Compressing backup..."
    
    cd "$BACKUP_DIR"
    
    local compressed_backup="${BACKUP_NAME}.tar.gz"
    
    tar -czf "$compressed_backup" "$BACKUP_NAME"
    
    if [ $? -eq 0 ]; then
        local original_size=$(du -sh "$BACKUP_NAME" | cut -f1)
        local compressed_size=$(du -sh "$compressed_backup" | cut -f1)
        
        log_info "Backup compressed successfully."
        log_info "Original size: ${original_size}"
        log_info "Compressed size: ${compressed_size}"
        log_info "Compression ratio: $(echo "scale=2; $(du -s "$BACKUP_NAME" | cut -f1) * 100 / $(du -s "$compressed_backup" | cut -f1)" | bc)%"
        
        # Remove uncompressed backup directory
        rm -rf "$BACKUP_NAME"
        
        echo "${BACKUP_DIR}/${compressed_backup}"
    else
        log_error "Backup compression failed."
        return 1
    fi
}

# Function to cleanup old backups
cleanup_old_backups() {
    log_info "Cleaning up old backups (keeping last ${KEEP_BACKUPS})..."
    
    cd "$BACKUP_DIR"
    
    # Count total backups
    local backup_count=$(ls -1 ${BACKUP_TYPE}_*.tar.gz 2>/dev/null | wc -l)
    
    if [ $backup_count -le $KEEP_BACKUPS ]; then
        log_info "Total backups: ${backup_count} (within limit of ${KEEP_BACKUPS})"
        return
    fi
    
    # Remove oldest backups
    local backups_to_remove=$((backup_count - KEEP_BACKUPS))
    
    log_info "Removing ${backups_to_remove} oldest backups..."
    
    ls -1t ${BACKUP_TYPE}_*.tar.gz 2>/dev/null | tail -n $backups_to_remove | while read backup; do
        log_info "Removing old backup: ${backup}"
        rm -f "$backup"
    done
    
    log_info "Cleanup completed."
}

# Function to verify backup
verify_backup() {
    local backup_file=$1
    
    log_info "Verifying backup: ${backup_file}"
    
    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: ${backup_file}"
        return 1
    fi
    
    # Test archive integrity
    if ! tar -tzf "$backup_file" >/dev/null 2>&1; then
        log_error "Backup archive is corrupted or invalid."
        return 1
    fi
    
    # Check for essential files
    local essential_files=(
        "postgres/postgres_backup_*.sql.gz"
        "config/.env"
        "config/docker-compose.yml"
    )
    
    for pattern in "${essential_files[@]}"; do
        if ! tar -tzf "$backup_file" | grep -q "$pattern"; then
            log_warn "Expected file not found in backup: ${pattern}"
        fi
    done
    
    log_info "Backup verification completed successfully."
    return 0
}

# Function to show backup summary
show_summary() {
    local backup_file=$1
    
    log_info "Backup Summary"
    log_info "=============="
    
    local backup_size=$(du -h "$backup_file" | cut -f1)
    local backup_date=$(stat -c %y "$backup_file" 2>/dev/null || stat -f "%Sm" "$backup_file" 2>/dev/null)
    
    log_info "Backup file: ${backup_file}"
    log_info "Size: ${backup_size}"
    log_info "Date: ${backup_date}"
    
    # List backup contents
    log_info "Contents:"
    tar -tzf "$backup_file" | head -20
    
    local total_files=$(tar -tzf "$backup_file" | wc -l)
    log_info "Total files: ${total_files}"
}

# Main backup function
main() {
    log_info "Starting backup process..."
    log_info "Log file: ${LOG_FILE}"
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --type)
                BACKUP_TYPE="$2"
                shift 2
                ;;
            --name)
                BACKUP_NAME="$2"
                shift 2
                ;;
            --keep)
                KEEP_BACKUPS="$2"
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
            --no-compress)
                NO_COMPRESS=true
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --type TYPE         Backup type (manual, scheduled, pre-deploy)"
                echo "  --name NAME         Custom backup name"
                echo "  --keep N            Keep last N backups (default: 30)"
                echo "  --skip-postgres     Skip PostgreSQL backup"
                echo "  --skip-minio        Skip MinIO backup"
                echo "  --skip-config       Skip configuration backup"
                echo "  --no-compress       Don't compress backup"
                echo "  --help              Show this help message"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Execute backup steps
    check_prerequisites
    load_env
    create_backup_dir
    
    if [ "${SKIP_POSTGRES:-false}" != "true" ]; then
        backup_postgres
    fi
    
    if [ "${SKIP_MINIO:-false}" != "true" ]; then
        backup_minio || true  # Continue even if MinIO backup fails
    fi
    
    if [ "${SKIP_CONFIG:-false}" != "true" ]; then
        backup_config
    fi
    
    local backup_file=""
    
    if [ "${NO_COMPRESS:-false}" != "true" ]; then
        backup_file=$(compress_backup)
    else
        backup_file="$BACKUP_PATH"
    fi
    
    if verify_backup "$backup_file"; then
        show_summary "$backup_file"
    fi
    
    cleanup_old_backups
    
    log_info "Backup process completed successfully!"
    log_info "Backup location: ${backup_file}"
}

# Trap errors
trap 'log_error "Backup failed at line $LINENO"' ERR

# Run main function
main "$@"

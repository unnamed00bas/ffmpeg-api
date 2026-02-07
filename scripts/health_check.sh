#!/bin/bash

# Health check script for FFmpeg API
# This script performs health checks on all services

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
LOG_FILE="${LOG_DIR}/health_check_$(date +%Y%m%d_%H%M%S).log"
ENV_FILE="${PROJECT_DIR}/.env"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Default values
API_HEALTH_URL="${HEALTH_CHECK_URL:-http://localhost:8000/api/v1/health}"
MAX_RETRIES=30
RETRY_DELAY=3
VERBOSE=false

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
    
    if ! command_exists curl; then
        log_error "curl is not installed"
        missing=1
    fi
    
    if ! command_exists docker; then
        log_error "Docker is not installed"
        missing=1
    fi
    
    if ! command_exists docker-compose; then
        log_error "Docker Compose is not installed"
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
        
        # Set health check URL from environment if available
        if [ -n "${API_BASE_URL:-}" ]; then
            API_HEALTH_URL="${API_BASE_URL}/api/v1/health"
        fi
        
        log_info "Environment variables loaded successfully."
    else
        log_warn "Environment file not found: $ENV_FILE"
    fi
}

# Function to check container status
check_container() {
    local container_name=$1
    local container_status
    
    container_status=$(docker-compose ps -q "$container_name" | xargs -r docker inspect -f '{{.State.Status}}' 2>/dev/null || echo "")
    
    if [ "$container_status" == "running" ]; then
        if [ "$VERBOSE" == "true" ]; then
            log_info "Container ${container_name}: ${GREEN}running${NC}"
        fi
        return 0
    else
        log_error "Container ${container_name}: ${RED}${container_status:-not found}${NC}"
        return 1
    fi
}

# Function to check API health
check_api_health() {
    log_info "Checking API health..."
    
    local attempt=0
    local response
    local http_code
    
    while [ $attempt -lt $MAX_RETRIES ]; do
        response=$(curl -s -w "\n%{http_code}" "$API_HEALTH_URL" 2>&1)
        http_code=$(echo "$response" | tail -n1)
        body=$(echo "$response" | sed '$d')
        
        if [ "$http_code" == "200" ]; then
            log_info "API health check: ${GREEN}PASSED${NC}"
            
            if [ "$VERBOSE" == "true" ]; then
                log_debug "API Response: $body"
            fi
            return 0
        fi
        
        attempt=$((attempt + 1))
        log_debug "Health check attempt ${attempt}/${MAX_RETRIES} failed (HTTP ${http_code}). Retrying..."
        sleep $RETRY_DELAY
    done
    
    log_error "API health check: ${RED}FAILED${NC} (HTTP ${http_code})"
    return 1
}

# Function to check PostgreSQL health
check_postgres_health() {
    log_info "Checking PostgreSQL health..."
    
    local postgres_user="${POSTGRES_USER:-postgres_user}"
    local postgres_db="${POSTGRES_DB:-ffmpeg_api}"
    local attempt=0
    local result
    
    while [ $attempt -lt $MAX_RETRIES ]; do
        result=$(docker-compose exec -T postgres pg_isready -U "$postgres_user" 2>&1 || echo "")
        
        if echo "$result" | grep -q "accepting connections"; then
            log_info "PostgreSQL health check: ${GREEN}PASSED${NC}"
            
            # Additional check: try to query the database
            local query_result=$(docker-compose exec -T postgres psql -U "$postgres_user" -d "$postgres_db" -c "SELECT 1;" 2>/dev/null || echo "")
            
            if echo "$query_result" | grep -q "1"; then
                if [ "$VERBOSE" == "true" ]; then
                    log_debug "PostgreSQL query test: ${GREEN}PASSED${NC}"
                fi
            fi
            
            return 0
        fi
        
        attempt=$((attempt + 1))
        log_debug "PostgreSQL health check attempt ${attempt}/${MAX_RETRIES} failed. Retrying..."
        sleep $RETRY_DELAY
    done
    
    log_error "PostgreSQL health check: ${RED}FAILED${NC}"
    return 1
}

# Function to check Redis health
check_redis_health() {
    log_info "Checking Redis health..."
    
    local attempt=0
    local result
    
    while [ $attempt -lt $MAX_RETRIES ]; do
        result=$(docker-compose exec -T redis redis-cli ping 2>&1 || echo "")
        
        if [ "$result" == "PONG" ]; then
            log_info "Redis health check: ${GREEN}PASSED${NC}"
            return 0
        fi
        
        attempt=$((attempt + 1))
        log_debug "Redis health check attempt ${attempt}/${MAX_RETRIES} failed. Retrying..."
        sleep $RETRY_DELAY
    done
    
    log_error "Redis health check: ${RED}FAILED${NC}"
    return 1
}

# Function to check MinIO health
check_minio_health() {
    log_info "Checking MinIO health..."
    
    local attempt=0
    local http_code
    
    while [ $attempt -lt $MAX_RETRIES ]; do
        http_code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:9000/minio/health/live 2>&1 || echo "000")
        
        if [ "$http_code" == "200" ]; then
            log_info "MinIO health check: ${GREEN}PASSED${NC}"
            return 0
        fi
        
        attempt=$((attempt + 1))
        log_debug "MinIO health check attempt ${attempt}/${MAX_RETRIES} failed (HTTP ${http_code}). Retrying..."
        sleep $RETRY_DELAY
    done
    
    log_error "MinIO health check: ${RED}FAILED${NC}"
    return 1
}

# Function to check Celery worker health
check_celery_health() {
    log_info "Checking Celery worker health..."
    
    local attempt=0
    local result
    
    while [ $attempt -lt $MAX_RETRIES ]; do
        result=$(docker-compose exec -T worker celery -A app.queue.celery_app inspect ping 2>&1 || echo "")
        
        if echo "$result" | grep -q "pong"; then
            log_info "Celery worker health check: ${GREEN}PASSED${NC}"
            return 0
        fi
        
        attempt=$((attempt + 1))
        log_debug "Celery worker health check attempt ${attempt}/${MAX_RETRIES} failed. Retrying..."
        sleep $RETRY_DELAY
    done
    
    log_warn "Celery worker health check: ${YELLOW}FAILED${NC} (worker may not be ready yet)"
    return 0  # Don't fail the entire health check if Celery is slow
}

# Function to check Flower health
check_flower_health() {
    log_info "Checking Flower health..."
    
    local attempt=0
    local http_code
    
    while [ $attempt -lt $MAX_RETRIES ]; do
        http_code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5555 2>&1 || echo "000")
        
        if [ "$http_code" == "200" ]; then
            log_info "Flower health check: ${GREEN}PASSED${NC}"
            return 0
        fi
        
        attempt=$((attempt + 1))
        log_debug "Flower health check attempt ${attempt}/${MAX_RETRIES} failed (HTTP ${http_code}). Retrying..."
        sleep $RETRY_DELAY
    done
    
    log_warn "Flower health check: ${YELLOW}FAILED${NC} (Flower may not be enabled)"
    return 0  # Don't fail the entire health check if Flower is not running
}

# Function to check Prometheus health
check_prometheus_health() {
    log_info "Checking Prometheus health..."
    
    local attempt=0
    local http_code
    
    while [ $attempt -lt $MAX_RETRIES ]; do
        http_code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:9090/-/healthy 2>&1 || echo "000")
        
        if [ "$http_code" == "200" ]; then
            log_info "Prometheus health check: ${GREEN}PASSED${NC}"
            return 0
        fi
        
        attempt=$((attempt + 1))
        log_debug "Prometheus health check attempt ${attempt}/${MAX_RETRIES} failed (HTTP ${http_code}). Retrying..."
        sleep $RETRY_DELAY
    done
    
    log_warn "Prometheus health check: ${YELLOW}FAILED${NC}"
    return 0  # Don't fail the entire health check if Prometheus is not running
}

# Function to check Grafana health
check_grafana_health() {
    log_info "Checking Grafana health..."
    
    local attempt=0
    local http_code
    
    while [ $attempt -lt $MAX_RETRIES ]; do
        http_code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/health 2>&1 || echo "000")
        
        if [ "$http_code" == "200" ]; then
            log_info "Grafana health check: ${GREEN}PASSED${NC}"
            return 0
        fi
        
        attempt=$((attempt + 1))
        log_debug "Grafana health check attempt ${attempt}/${MAX_RETRIES} failed (HTTP ${http_code}). Retrying..."
        sleep $RETRY_DELAY
    done
    
    log_warn "Grafana health check: ${YELLOW}FAILED${NC}"
    return 0  # Don't fail the entire health check if Grafana is not running
}

# Function to show container logs on failure
show_container_logs() {
    local container_name=$1
    local lines=${2:-50}
    
    log_info "Showing last ${lines} lines of ${container_name} logs:"
    docker-compose logs --tail="$lines" "$container_name" | tee -a "$LOG_FILE"
}

# Function to show health check summary
show_summary() {
    log_info "Health Check Summary"
    log_info "===================="
    
    cd "$PROJECT_DIR"
    
    log_info "Running containers:"
    docker-compose ps | tee -a "$LOG_FILE"
    
    log_info ""
    log_info "Service URLs:"
    log_info "  API:      http://localhost:8000"
    log_info "  API Docs: http://localhost:8000/docs"
    log_info "  MinIO:    http://localhost:9000"
    log_info "  Flower:   http://localhost:5555"
    log_info "  Grafana:  http://localhost:3000"
    log_info "  Prometheus: http://localhost:9090"
}

# Main health check function
main() {
    log_info "Starting health check process..."
    log_info "Log file: ${LOG_FILE}"
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --url)
                API_HEALTH_URL="$2"
                shift 2
                ;;
            --retries)
                MAX_RETRIES="$2"
                shift 2
                ;;
            --delay)
                RETRY_DELAY="$2"
                shift 2
                ;;
            --verbose|-v)
                VERBOSE=true
                shift
                ;;
            --quick)
                MAX_RETRIES=5
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --url URL           Custom API health check URL"
                echo "  --retries N         Number of retries (default: 30)"
                echo "  --delay SECONDS     Delay between retries (default: 3)"
                echo "  --verbose, -v       Show detailed output"
                echo "  --quick             Quick health check (5 retries)"
                echo "  --help              Show this help message"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Execute health checks
    check_prerequisites
    load_env
    
    local failed_checks=0
    
    # Check all containers
    local containers=("postgres" "redis" "minio" "api" "worker" "beat" "flower" "prometheus" "grafana")
    
    log_info "Checking container status..."
    for container in "${containers[@]}"; do
        if ! check_container "$container"; then
            failed_checks=$((failed_checks + 1))
        fi
    done
    
    # Perform health checks on critical services
    if ! check_postgres_health; then
        failed_checks=$((failed_checks + 1))
        show_container_logs "postgres"
    fi
    
    if ! check_redis_health; then
        failed_checks=$((failed_checks + 1))
        show_container_logs "redis"
    fi
    
    if ! check_minio_health; then
        failed_checks=$((failed_checks + 1))
        show_container_logs "minio"
    fi
    
    if ! check_api_health; then
        failed_checks=$((failed_checks + 1))
        show_container_logs "api"
    fi
    
    # Optional health checks (don't fail the entire check)
    check_celery_health || true
    check_flower_health || true
    check_prometheus_health || true
    check_grafana_health || true
    
    show_summary
    
    if [ $failed_checks -gt 0 ]; then
        log_error "Health check completed with ${failed_checks} failed checks."
        exit 1
    else
        log_info "All health checks passed successfully!"
        exit 0
    fi
}

# Trap errors
trap 'log_error "Health check failed at line $LINENO"' ERR

# Run main function
main "$@"

# Deployment and Maintenance Scripts

This directory contains scripts for deploying, maintaining, and backing up the FFmpeg API application.

## Scripts Overview

### Core Deployment Scripts

#### `deploy.sh` - Main Deployment Script
Automated deployment script that handles the complete deployment process.

**Usage:**
```bash
./scripts/deploy.sh [OPTIONS]
```

**Options:**
- `--skip-backup` - Skip pre-deployment backup
- `--skip-health-check` - Skip health check after deployment

**Example:**
```bash
./scripts/deploy.sh
./scripts/deploy.sh --skip-backup
```

**What it does:**
1. Checks prerequisites (Docker, Docker Compose, Git)
2. Loads environment variables
3. Creates pre-deployment backup
4. Pulls latest code from repository
5. Builds Docker images
6. Stops old containers
7. Runs database migrations
8. Starts new containers
9. Performs health checks
10. Cleans up old Docker images
11. Shows deployment summary

---

#### `rollback.sh` - Rollback Script
Rolls back the application to the previous version.

**Usage:**
```bash
./scripts/rollback.sh [OPTIONS]
```

**Options:**
- `--skip-health-check` - Skip health check after rollback
- `--to-tag TAG` - Rollback to specific Git tag
- `--help` - Show help message

**Example:**
```bash
./scripts/rollback.sh
./scripts/rollback.sh --to-tag rollback_point_20250205_120000
./scripts/rollback.sh --skip-health-check
```

**What it does:**
1. Checks prerequisites
2. Backs up current version before rollback
3. Gets previous commit or specified tag
4. Checks out previous version
5. Rebuilds and restarts containers
6. Rolls back database migrations
7. Performs health checks
8. Shows rollback summary

---

### Backup and Restore Scripts

#### `backup.sh` - Backup Script
Creates backups of PostgreSQL, MinIO, and configuration.

**Usage:**
```bash
./scripts/backup.sh [OPTIONS]
```

**Options:**
- `--type TYPE` - Backup type (manual, scheduled, pre-deploy)
- `--name NAME` - Custom backup name
- `--keep N` - Keep last N backups (default: 30)
- `--skip-postgres` - Skip PostgreSQL backup
- `--skip-minio` - Skip MinIO backup
- `--skip-config` - Skip configuration backup
- `--no-compress` - Don't compress backup
- `--help` - Show help message

**Example:**
```bash
./scripts/backup.sh
./scripts/backup.sh --type scheduled --keep 7
./scripts/backup.sh --name my_backup --no-compress
```

**What it backs up:**
- PostgreSQL database dumps
- MinIO data files
- Environment configuration
- Docker Compose files
- Prometheus/Grafana configurations
- Git state (commit hash, branch)

**Backup retention:**
- Keeps last 30 backups by default
- Configurable via `--keep` option
- Automatic cleanup of old backups

---

#### `restore.sh` - Restore Script
Restores application from backup.

**Usage:**
```bash
./scripts/restore.sh [OPTIONS] [BACKUP_NAME]
```

**Options:**
- `--backup NAME` - Specify backup name or path
- `--skip-postgres` - Skip PostgreSQL restore
- `--skip-minio` - Skip MinIO restore
- `--skip-config` - Skip configuration restore
- `--skip-services-start` - Skip starting services after restore
- `--skip-health-check` - Skip health check after restore
- `--help` - Show help message

**Example:**
```bash
./scripts/restore.sh
./scripts/restore.sh pre-deploy_20250205_120000.tar.gz
./scripts/restore.sh --skip-config /path/to/backup.tar.gz
```

**What it does:**
1. Finds and verifies backup integrity
2. Extracts backup archive
3. Restores PostgreSQL database
4. Restores MinIO data
5. Restores configuration files
6. Optionally restores Git state
7. Starts services
8. Performs health checks
9. Shows restore summary

---

#### `health_check.sh` - Health Check Script
Performs health checks on all application services.

**Usage:**
```bash
./scripts/health_check.sh [OPTIONS]
```

**Options:**
- `--url URL` - Custom API health check URL
- `--retries N` - Number of retries (default: 30)
- `--delay SECONDS` - Delay between retries (default: 3)
- `--verbose, -v` - Show detailed output
- `--quick` - Quick health check (5 retries)
- `--help` - Show help message

**Example:**
```bash
./scripts/health_check.sh
./scripts/health_check.sh --verbose
./scripts/health_check.sh --quick
./scripts/health_check.sh --url http://localhost:8000/api/v1/health
```

**What it checks:**
- Container status (running/stopped)
- PostgreSQL health and connectivity
- Redis health and connectivity
- MinIO health and connectivity
- API health endpoint
- Celery worker health
- Flower health (if enabled)
- Prometheus health (if enabled)
- Grafana health (if enabled)

---

## Setup and Configuration

### Prerequisites

All scripts require the following tools:
- Docker
- Docker Compose
- Git
- curl
- gzip
- tar

### Environment Variables

Scripts use environment variables from `.env` file:

```bash
# Database
POSTGRES_USER=postgres_user
POSTGRES_PASSWORD=postgres_password
POSTGRES_DB=ffmpeg_api

# MinIO
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_BUCKET_NAME=ffmpeg-files

# API
API_BASE_URL=http://localhost:8000
HEALTH_CHECK_URL=http://localhost:8000/api/v1/health
```

### Making Scripts Executable

Make all scripts executable:
```bash
chmod +x scripts/*.sh
```

---

## Deployment Workflow

### Standard Deployment

1. **Pre-deployment backup** (automatic)
2. **Pull latest code**
3. **Build Docker images**
4. **Stop old containers**
5. **Run migrations**
6. **Start new containers**
7. **Health check**
8. **Cleanup**

### Rollback Workflow

1. **Backup current version**
2. **Get previous commit**
3. **Checkout previous version**
4. **Rebuild containers**
5. **Rollback migrations**
6. **Health check**

---

## Backup Strategy

### Backup Types

1. **Manual** - On-demand backups
2. **Scheduled** - Automated backups (e.g., daily)
3. **Pre-deploy** - Created automatically before deployments

### Backup Contents

Each backup includes:
- PostgreSQL database dump
- MinIO data files
- Environment configuration
- Docker Compose files
- Monitoring configurations
- Git state information

### Backup Retention

- Default: Keep last 30 backups
- Configurable via `--keep` option
- Automatic cleanup of old backups

---

## Monitoring and Logging

### Log Files

All scripts create detailed log files:
- `deploy_YYYYMMDD_HHMMSS.log`
- `rollback_YYYYMMDD_HHMMSS.log`
- `backup_YYYYMMDD_HHMMSS.log`
- `restore_YYYYMMDD_HHMMSS.log`
- `health_check_YYYYMMDD_HHMMSS.log`

Logs are stored in the `logs/` directory.

### Log Levels

Scripts use color-coded log levels:
- **INFO** (Green) - Normal operations
- **WARN** (Yellow) - Non-critical warnings
- **ERROR** (Red) - Errors and failures
- **DEBUG** (Blue) - Detailed debugging info

---

## CI/CD Integration

### GitHub Actions

Scripts are integrated with GitHub Actions workflows:

- **CI Pipeline** (`.github/workflows/ci.yml`):
  - Linting (Black, Flake8, MyPy)
  - Tests with coverage (> 80%)
  - Docker image builds
  - Security scanning

- **Deploy Pipeline** (`.github/workflows/deploy.yml`):
  - Pre-deployment backup
  - Code deployment
  - Database migrations
  - Health checks
  - Automatic rollback on failure

### Required GitHub Secrets

Configure these secrets in GitHub:

```
PRODUCTION_HOST=your-server.com
PRODUCTION_SSH_PRIVATE_KEY=-----BEGIN OPENSSH PRIVATE KEY-----...
DEPLOY_USER=deploy

STAGING_HOST=staging.your-server.com
STAGING_SSH_PRIVATE_KEY=-----BEGIN OPENSSH PRIVATE KEY-----...

CODECOV_TOKEN=your-codecov-token
```

---

## Troubleshooting

### Common Issues

**Script execution failed with permission denied:**
```bash
chmod +x scripts/*.sh
```

**Docker container not starting:**
```bash
docker-compose logs <service_name>
```

**Health check failed:**
```bash
./scripts/health_check.sh --verbose
```

**Backup restore failed:**
```bash
# Verify backup integrity
tar -tzf backup.tar.gz

# Check logs
cat logs/restore_*.log
```

### Getting Help

Use `--help` flag with any script:
```bash
./scripts/deploy.sh --help
./scripts/backup.sh --help
./scripts/restore.sh --help
```

---

## Security Considerations

### SSH Keys

- Use SSH key-based authentication
- Store private keys in GitHub Secrets
- Use restrictive permissions (600)
- Regularly rotate SSH keys

### Environment Variables

- Never commit `.env` files
- Use `.env.example` as template
- Store sensitive data in secrets
- Rotate passwords regularly

### Backups

- Encrypt backups for storage
- Store backups in secure locations
- Test restore procedures regularly
- Implement backup retention policies

---

## Maintenance Tasks

### Daily Tasks

- Review logs for errors
- Check disk space usage
- Monitor service health

### Weekly Tasks

- Test backup restore procedures
- Review and clean old logs
- Update dependencies

### Monthly Tasks

- Security audit
- Performance review
- Capacity planning
- Disaster recovery testing

---

## Best Practices

1. **Always test in staging first**
2. **Keep backups before major changes**
3. **Monitor logs after deployments**
4. **Document custom configurations**
5. **Regular security updates**
6. **Test disaster recovery procedures**

---

## Support

For issues or questions:
- Check logs in `logs/` directory
- Review this documentation
- Check GitHub Issues
- Contact DevOps team

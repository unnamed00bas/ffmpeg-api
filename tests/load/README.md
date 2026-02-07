# Load Testing with Locust

This directory contains Locust-based load tests for the FFmpeg API project.

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Running Tests](#running-tests)
- [User Types](#user-types)
- [Metrics and Targets](#metrics-and-targets)
- [Analyzing Results](#analyzing-results)
- [Optimization Recommendations](#optimization-recommendations)
- [Docker Support](#docker-support)
- [Advanced Usage](#advanced-usage)
- [Troubleshooting](#troubleshooting)

## Installation

### Prerequisites

- Python 3.8+
- Access to the FFmpeg API (running locally or remotely)
- Optional: Docker for containerized testing

### Install Locust

```bash
pip install locust
```

Or install with additional dependencies:

```bash
pip install locust[gevent]
```

For production load testing, install additional packages:

```bash
pip install locust[gevent,psutil,pycurl]
```

## Quick Start

### 1. Start the FFmpeg API

Make sure the API is running. You can start it using Docker Compose:

```bash
docker-compose up -d api postgres redis minio
```

### 2. Run Load Tests in Headless Mode

```bash
cd tests/load
locust -f locustfile.py --headless --users 100 --spawn-rate 10 --run-time 2m --host http://localhost:8000
```

This will:
- Launch 100 users
- Spawn new users at a rate of 10 per second
- Run for 2 minutes
- Target http://localhost:8000

### 3. Run Load Tests with Web UI

```bash
cd tests/load
locust -f locustfile.py --host http://localhost:8000
```

Then open your browser to: http://localhost:8089

## Running Tests

### Standard Mode (CLI)

```bash
# Basic test with 100 users
locust -f locustfile.py --headless \
  --users 100 \
  --spawn-rate 10 \
  --run-time 2m \
  --host http://localhost:8000
```

### Web Interface Mode

```bash
# Start with web UI
locust -f locustfile.py --host http://localhost:8000

# Then navigate to: http://localhost:8089
```

In the web interface:
1. Set the number of users (e.g., 100)
2. Set spawn rate (e.g., 10 users/second)
3. Set run time (e.g., 2m) or leave empty for manual control
4. Click "Start swarming"

### Distributed Mode (Master/Worker)

For large-scale load testing across multiple machines:

**Master:**

```bash
# Start master
locust -f locustfile.py --master --host http://localhost:8000

# Or with CLI
locust -f locustfile.py --master --headless \
  --users 1000 \
  --spawn-rate 50 \
  --run-time 10m \
  --host http://localhost:8000
```

**Workers (run on each worker machine):**

```bash
# Connect worker to master
locust -f locustfile.py --worker --master-host <master-ip>

# Or use environment variables
LOCUST_MASTER_HOST=<master-ip> locust -f locustfile.py --worker
```

### Different Test Profiles

```bash
# Small smoke test
locust -f locustfile.py --headless \
  --users 10 \
  --spawn-rate 1 \
  --run-time 30s \
  --host http://localhost:8000

# Medium load test
locust -f locustfile.py --headless \
  --users 100 \
  --spawn-rate 10 \
  --run-time 5m \
  --host http://localhost:8000

# High load stress test
locust -f locustfile.py --headless \
  --users 500 \
  --spawn-rate 50 \
  --run-time 10m \
  --host http://localhost:8000

# Endurance test
locust -f locustfile.py --headless \
  --users 100 \
  --spawn-rate 5 \
  --run-time 1h \
  --host http://localhost:8000
```

### Environment Variables

```bash
# Set base URL via environment
export LOCUST_BASE_URL=http://localhost:8000
locust -f locustfile.py --headless --users 100

# Or inline
LOCUST_BASE_URL=http://api.example.com locust -f locustfile.py --headless --users 100
```

## User Types

### FFmpegAPIUser

Simulates regular users viewing content:

**Task Weights:**
- `get_tasks`: Weight 3 (most frequent)
- `get_files`: Weight 2
- `get_user_stats`: Weight 1 (least frequent)

**Behavior:**
- Registers/logs in automatically
- Uploads 2 test video files on start
- Waits 1-3 seconds between tasks
- Browses through tasks, files, and stats

**Endpoints Hit:**
- GET `/api/v1/tasks`
- GET `/api/v1/files`
- GET `/api/v1/users/me/stats`

### CreateTaskUser

Simulates active users creating processing tasks:

**Task Weights:**
- `create_join_task`: Weight 1
- `create_audio_overlay_task`: Weight 1

**Behavior:**
- Registers/logs in automatically
- Uploads 3 video files and 1 audio file on start
- Waits 2-5 seconds between tasks
- Creates join and audio overlay tasks

**Endpoints Hit:**
- POST `/api/v1/tasks/join`
- POST `/api/v1/tasks/audio-overlay`

## Metrics and Targets

### Key Metrics

| Metric | Description |
|--------|-------------|
| **RPS** | Requests Per Second - throughput |
| **Response Time** | Time from request to response |
| **p50** | Median response time (50th percentile) |
| **p95** | 95% of requests complete faster than this |
| **p99** | 99% of requests complete faster than this |
| **Failure Rate** | Percentage of failed requests |
| **CPU Usage** | System CPU utilization during test |
| **RAM Usage** | Memory consumption during test |
| **Disk I/O** | Disk read/write operations |
| **Network I/O** | Network bandwidth usage |

### Performance Targets

| Metric | Target | Threshold |
|--------|--------|-----------|
| **Concurrent Requests** | 100+ | 100 minimum |
| **Failure Rate** | < 5% | 5% maximum |
| **p95 Response Time** | < 500ms | 500ms maximum |
| **p99 Response Time** | < 1000ms | 1000ms maximum |
| **Average Response Time** | < 200ms | 200ms maximum |

### System Resource Targets

| Resource | Target | Warning Threshold |
|----------|--------|-------------------|
| CPU Usage | < 70% | 85% warning |
| RAM Usage | < 80% | 90% warning |
| Disk I/O | < 80% capacity | 90% warning |
| Network Bandwidth | < 70% capacity | 85% warning |

## Analyzing Results

### Using Web UI

The web interface provides real-time visualization:

1. **Charts Tab:**
   - Total requests per second (RPS)
   - Response times
   - Number of users
   - Failure rate

2. **Statistics Tab:**
   - Request count by endpoint
   - Min/Avg/Max response times
   - Response time percentiles (p50, p95, p99)
   - Failure rate per endpoint

3. **Failures Tab:**
   - All failed requests
   - Error messages
   - Stack traces

### Using CLI Summary

When running in `--headless` mode, Locust prints a summary on completion:

```
Name                    # reqs      # fails |     Avg     Min     Max    Median |   req/s  failures/s
----------------------------------------------------------------------------------------------
GET /api/v1/tasks          450     0(0.00%) |     145      45     520       135 |    7.50        0.00
GET /api/v1/files          300     0(0.00%) |     180      60     610       165 |    5.00        0.00
GET /api/v1/users/me/stats  150     0(0.00%) |     200      80     750       185 |    2.50        0.00
POST /api/v1/tasks/join     100     2(2.00%)|     320     150    1200       280 |    1.67        0.03
----------------------------------------------------------------------------------------------
Aggregated                  1000     2(0.20%)|     176      45    1200       155 |   16.67        0.03

Response time percentiles (approximated)
  Type      Name                    50%    66%    80%    90%    95%    98%    99%   100%
----------------------------------------------------------------------------------------------
            GET /api/v1/tasks       135    140    150    165    190    240    280     520
            GET /api/v1/files       165    175    185    200    225    280    340     610
            GET /api/v1/users/me/stats 185    195    210    240    280    350    450     750
            POST /api/v1/tasks/join  280    300    340    400    480    650    800    1200
----------------------------------------------------------------------------------------------
            Aggregated               155    165    175    190    220    270    340    1200
```

### Custom Analysis

Locust automatically generates a summary with recommendations at the end of each test:

```
================================================================================
LOAD TEST SUMMARY
================================================================================

Total Requests: 1000
Total Failures: 2
Failure Rate: 0.20%
Total RPS: 16.67

Response Time Statistics:
  Min: 45.00 ms
  Average: 176.00 ms
  Median (p50): 155.00 ms
  p95: 220.00 ms
  p99: 340.00 ms
  Max: 1200.00 ms

--------------------------------------------------------------------------------
TARGET ANALYSIS
--------------------------------------------------------------------------------
✓ Failure rate (0.20%) meets target (< 5%)
✓ p95 response time (220.00 ms) meets target (< 500ms)
✓ p99 response time (340.00 ms) meets target (< 1000ms)

--------------------------------------------------------------------------------
OPTIMIZATION RECOMMENDATIONS
--------------------------------------------------------------------------------
✓ Good throughput achieved
...
```

## Optimization Recommendations

### High Failure Rate (> 5%)

**Symptoms:**
- Many HTTP 500 errors
- Connection timeouts
- Database errors

**Investigation Steps:**

1. **Check Logs:**
```bash
docker-compose logs api | tail -100
docker-compose logs worker | tail -100
```

2. **Monitor Resources:**
```bash
docker stats
```

3. **Check Database:**
```bash
docker-compose exec postgres psql -U postgres_user -d ffmpeg_api -c "SELECT COUNT(*) FROM pg_stat_activity;"
```

4. **Check Redis:**
```bash
docker-compose exec redis redis-cli INFO clients
```

**Possible Solutions:**
- Increase database connection pool size
- Add database indexes for slow queries
- Scale horizontally with multiple API instances
- Implement circuit breakers for external services
- Add retry logic for transient failures

### Slow Response Times (p95 > 500ms or p99 > 1000ms)

**Symptoms:**
- High latency on all requests
- Spikes on specific endpoints

**Investigation Steps:**

1. **Profile API Endpoints:**
```python
# Add profiling to slow endpoints
import cProfile
import pstats

# In your endpoint handler
profiler = cProfile.Profile()
profiler.enable()
# ... endpoint code ...
profiler.disable()
profiler.dump_stats('profile.stats')
```

2. **Check Database Queries:**
```python
# Enable query logging in PostgreSQL
docker-compose exec postgres psql -U postgres_user -d ffmpeg_api -c "
ALTER SYSTEM SET log_statement = 'all';
SELECT pg_reload_conf();
"
```

3. **Monitor Celery Queue:**
```bash
# Check Flower dashboard
open http://localhost:5555
```

**Possible Solutions:**
- Add caching layer (Redis) for frequently accessed data
- Implement database query optimization:
  - Add proper indexes
  - Use `select_related`/`joinedload` for ORM queries
  - Implement pagination for large result sets
- Implement read replicas for database read operations
- Use connection pooling (SQLAlchemy `pool_size`, `max_overflow`)
- Implement async operations for I/O-bound tasks
- Add CDN for static assets
- Optimize FFmpeg command parameters

### Low Throughput (< 100 RPS)

**Symptoms:**
- Can't achieve target RPS
- CPU underutilized but still slow

**Investigation Steps:**

1. **Check Worker Processes:**
```bash
# Check Uvicorn worker configuration
docker-compose exec api ps aux | grep uvicorn
```

2. **Analyze Bottlenecks:**
```python
# Use cProfile to identify slow functions
```

**Possible Solutions:**
- Increase worker processes:
```python
# In Dockerfile.api or entrypoint
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```
- Use Gunicorn with Uvicorn workers:
```python
CMD ["gunicorn", "app.main:app", "--worker-class", "uvicorn.workers.UvicornWorker", "--workers", "4", "--bind", "0.0.0.0:8000"]
```
- Implement request batching
- Reduce unnecessary middleware
- Optimize database queries
- Use connection pooling

### Database Optimization

```sql
-- Add indexes for commonly queried columns
CREATE INDEX idx_tasks_user_id ON tasks(user_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_files_user_id ON files(user_id);

-- Analyze query performance
EXPLAIN ANALYZE SELECT * FROM tasks WHERE user_id = 1 AND status = 'pending';
```

### Caching Strategy

```python
# Add Redis caching for expensive operations
from app.cache.cache_service import CacheService

@cached(ttl=300)  # Cache for 5 minutes
async def get_user_files_count(user_id: int):
    # Database query
    pass
```

## Docker Support

### Run Load Tests in Docker

Create a `docker-compose.load.yml` file (provided):

```bash
# Start load testing environment
docker-compose -f docker-compose.load.yml up -d

# Run load tests
docker-compose -f docker-compose.load.yml exec load-tester locust -f /app/locustfile.py --headless --users 100 --spawn-rate 10 --run-time 2m --host http://api:8000
```

### Load Testing Docker Compose Configuration

The provided `docker-compose.load.yml` includes:

- **API Service**: FFmpeg API application
- **PostgreSQL**: Database
- **Redis**: Queue and cache
- **MinIO**: Object storage

This ensures that the load tests run in an isolated environment similar to production.

## Advanced Usage

### Custom Test Scenarios

You can create custom user classes for different scenarios:

```python
class PowerUser(HttpUser):
    """User performing high-intensity operations"""
    wait_time = between(0.5, 1)  # Fast-paced
    
    @task(5)
    def intensive_operation(self):
        # More frequent operations
        pass

class BurstUser(HttpUser):
    """User that operates in bursts"""
    wait_time = constant(10)  # Wait 10s between bursts
    
    @task
    def burst_operations(self):
        for _ in range(10):  # Do 10 operations quickly
            self.create_task()
```

### Distributed Load Testing

For large-scale testing (10,000+ users):

1. **Master Node:**
```bash
locust -f locustfile.py --master \
  --expect-workers 10 \
  --users 10000 \
  --spawn-rate 100 \
  --host http://api.example.com
```

2. **Worker Nodes** (10 nodes):
```bash
locust -f locustfile.py --worker --master-host <master-ip>
```

### Result Export

Export results for analysis:

```bash
# Export to CSV
locust -f locustfile.py --headless \
  --csv=load_test_results \
  --users 100 --spawn-rate 10 --run-time 2m

# Export to HTML report
locust -f locustfile.py --headless \
  --html=load_test_report.html \
  --users 100 --spawn-rate 10 --run-time 2m
```

### Integration with CI/CD

Add to your CI/CD pipeline:

```yaml
# .github/workflows/load-test.yml
name: Load Test

on:
  schedule:
    - cron: '0 2 * * *'  # Run daily at 2 AM
  workflow_dispatch:

jobs:
  load-test:
    runs-on: ubuntu-latest
    services:
      api:
        image: ffmpeg-api:latest
        ports:
          - 8000:8000
    steps:
      - uses: actions/checkout@v3
      - name: Install Locust
        run: pip install locust
      - name: Run Load Test
        run: |
          cd tests/load
          locust -f locustfile.py --headless \
            --users 100 --spawn-rate 10 --run-time 5m \
            --csv=results --host http://localhost:8000
      - name: Upload Results
        uses: actions/upload-artifact@v3
        with:
          name: load-test-results
          path: tests/load/results*
```

## Troubleshooting

### Common Issues

#### "Connection refused" or "Unable to connect"

**Cause:** API not running or wrong URL

**Solution:**
```bash
# Check if API is running
curl http://localhost:8000/api/v1/health

# Verify correct host
locust -f locustfile.py --headless --host http://localhost:8000
```

#### "401 Unauthorized" errors

**Cause:** Token expiration or authentication issues

**Solution:**
- Check JWT token configuration
- Verify JWT_SECRET is set correctly
- Increase JWT_ACCESS_TOKEN_EXPIRE_MINUTES in settings

#### High memory usage

**Cause:** Too many users or memory leaks

**Solution:**
- Reduce number of users
- Check for memory leaks in API code
- Add memory limits:
```bash
locust -f locustfile.py --headless --users 100 \
  --memory-limit 2000  # Limit to 2GB
```

#### "Too many open files" error

**Cause:** File descriptor limit exceeded

**Solution:**
```bash
# Increase file descriptor limit (Linux/Mac)
ulimit -n 10000

# Or in Locust config
# Add to locustfile.py
import resource
resource.setrlimit(resource.RLIMIT_NOFILE, (10000, 10000))
```

### Debug Mode

Enable verbose logging:

```bash
locust -f locustfile.py --headless --loglevel DEBUG \
  --users 10 --spawn-rate 1 --run-time 1m
```

### Checking Test Fixtures

Ensure test files exist:

```bash
ls -lh tests/fixtures/
# Should see:
# test_video.mp4
# test_audio.mp3
```

If missing, generate them:

```bash
# Generate test video
ffmpeg -f lavfi -i testsrc=duration=5:size=320x240:rate=30 \
  -c:v libx264 -t 5 tests/fixtures/test_video.mp4

# Generate test audio
ffmpeg -f lavfi -i sine=frequency=1000:duration=5 \
  -c:a libmp3lame -b:a 128k tests/fixtures/test_audio.mp3
```

## Additional Resources

- [Locust Documentation](https://docs.locust.io/)
- [Locust GitHub](https://github.com/locustio/locust)
- [FFmpeg API Documentation](../../docs/API.md)
- [Architecture Documentation](../../docs/ARCHITECTURE.md)

## Support

For issues specific to the FFmpeg API load testing:
- Check the main API logs: `docker-compose logs api`
- Check worker logs: `docker-compose logs worker`
- Monitor Celery tasks: http://localhost:5555 (Flower)
- Check database status: `docker-compose exec postgres psql -U postgres_user -d ffmpeg_api`

---

**Last Updated:** 2026-02-05

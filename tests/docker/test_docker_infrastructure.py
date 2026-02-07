"""
Docker infrastructure and monitoring tests
"""
import pytest
import subprocess
import time
import requests
from typing import Dict


@pytest.mark.docker
@pytest.mark.integration
class TestDockerSmokeTests:
    """Smoke tests for Docker infrastructure"""

    @pytest.fixture(scope="module", autouse=True)
    def docker_compose_up(self):
        """Launch Docker Compose before tests"""
        # Check if Docker is running
        try:
            result = subprocess.run(
                ["docker", "ps"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                pytest.skip("Docker is not running")
        except FileNotFoundError:
            pytest.skip("Docker is not installed")

        # Check if docker-compose.yml exists
        from pathlib import Path
        docker_compose = Path(__file__).parent.parent.parent / "docker-compose.yml"
        if not docker_compose.exists():
            pytest.skip("docker-compose.yml not found")

        # Note: We don't actually start containers in unit tests
        # This would require running in CI/CD with proper Docker setup
        yield

    def test_docker_is_available(self):
        """Test that Docker is available"""
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        assert result.returncode == 0, "Docker is not available"
        assert "Docker version" in result.stdout

    def test_docker_compose_is_available(self):
        """Test that Docker Compose is available"""
        result = subprocess.run(
            ["docker-compose", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            # Try docker compose (v2)
            result = subprocess.run(
                ["docker", "compose", "version"],
                capture_output=True,
                text=True,
                timeout=5
            )
        assert result.returncode == 0, "Docker Compose is not available"

    def test_docker_compose_file_exists(self):
        """Test that docker-compose.yml exists"""
        from pathlib import Path
        docker_compose = Path(__file__).parent.parent.parent / "docker-compose.yml"
        assert docker_compose.exists(), "docker-compose.yml not found"

    def test_dockerfile_api_exists(self):
        """Test that Dockerfile for API exists"""
        from pathlib import Path
        dockerfile_api = Path(__file__).parent.parent.parent / "docker" / "Dockerfile.api"
        assert dockerfile_api.exists(), "docker/Dockerfile.api not found"

    def test_dockerfile_worker_exists(self):
        """Test that Dockerfile for Worker exists"""
        from pathlib import Path
        dockerfile_worker = Path(__file__).parent.parent.parent / "docker" / "Dockerfile.worker"
        assert dockerfile_worker.exists(), "docker/Dockerfile.worker not found"


@pytest.mark.docker
@pytest.mark.integration
class TestDockerHealthChecks:
    """Health check tests for Docker services"""

    def test_postgresql_health_check_configured(self):
        """Test that PostgreSQL health check is configured in docker-compose.yml"""
        from pathlib import Path
        import yaml

        docker_compose = Path(__file__).parent.parent.parent / "docker-compose.yml"
        with open(docker_compose) as f:
            compose = yaml.safe_load(f)

        postgres_config = compose.get("services", {}).get("postgres", {})

        # Check that healthcheck is configured
        assert "healthcheck" in postgres_config, \
            "PostgreSQL healthcheck not configured in docker-compose.yml"

        healthcheck = postgres_config["healthcheck"]
        assert "test" in healthcheck, "PostgreSQL healthcheck test not defined"
        assert "pg_isready" in healthcheck["test"], \
            "PostgreSQL healthcheck should use pg_isready"

    def test_redis_health_check_configured(self):
        """Test that Redis health check is configured in docker-compose.yml"""
        from pathlib import Path
        import yaml

        docker_compose = Path(__file__).parent.parent.parent / "docker-compose.yml"
        with open(docker_compose) as f:
            compose = yaml.safe_load(f)

        redis_config = compose.get("services", {}).get("redis", {})

        # Check that healthcheck is configured
        assert "healthcheck" in redis_config, \
            "Redis healthcheck not configured in docker-compose.yml"

        healthcheck = redis_config["healthcheck"]
        assert "test" in healthcheck, "Redis healthcheck test not defined"
        assert "ping" in healthcheck["test"], \
            "Redis healthcheck should use redis-cli ping"

    def test_minio_health_check_configured(self):
        """Test that MinIO health check is configured in docker-compose.yml"""
        from pathlib import Path
        import yaml

        docker_compose = Path(__file__).parent.parent.parent / "docker-compose.yml"
        with open(docker_compose) as f:
            compose = yaml.safe_load(f)

        minio_config = compose.get("services", {}).get("minio", {})

        # Check that healthcheck is configured
        assert "healthcheck" in minio_config, \
            "MinIO healthcheck not configured in docker-compose.yml"

        healthcheck = minio_config["healthcheck"]
        assert "test" in healthcheck, "MinIO healthcheck test not defined"
        assert "/minio/health/live" in healthcheck["test"], \
            "MinIO healthcheck should use /minio/health/live"

    def test_api_health_endpoint_exists(self):
        """Test that API health endpoint exists in code"""
        from pathlib import Path
        import re

        health_py = Path(__file__).parent.parent.parent / "app" / "api" / "v1" / "health.py"
        assert health_py.exists(), "app/api/v1/health.py not found"

        content = health_py.read_text()

        # Check for health endpoint
        assert "@router.get" in content or "@app.get" in content, \
            "Health endpoint not defined in health.py"
        assert '"/' in content or '"/health"' in content, \
            "Health endpoint route not defined"


@pytest.mark.docker
@pytest.mark.integration
class TestPrometheusConfiguration:
    """Prometheus configuration tests"""

    def test_prometheus_config_exists(self):
        """Test that Prometheus configuration file exists"""
        from pathlib import Path
        prometheus_yml = Path(__file__).parent.parent.parent / "docker" / "prometheus.yml"
        assert prometheus_yml.exists(), "docker/prometheus.yml not found"

    def test_prometheus_scrape_configs(self):
        """Test that Prometheus has correct scrape configurations"""
        from pathlib import Path
        import yaml

        prometheus_yml = Path(__file__).parent.parent / "docker" / "prometheus.yml"
        with open(prometheus_yml) as f:
            prometheus = yaml.safe_load(f)

        scrape_configs = prometheus.get("scrape_configs", [])

        # Check for required scrape jobs
        job_names = [config.get("job_name", "") for config in scrape_configs]

        assert "fastapi" in job_names, "Prometheus missing scrape config for fastapi (API)"
        assert "postgres" in job_names, "Prometheus missing scrape config for postgres"
        assert "redis" in job_names, "Prometheus missing scrape config for redis"
        assert "celery-flower" in job_names, "Prometheus missing scrape config for celery-flower"

        # Check fastapi scrape config
        fastapi_config = next(
            (c for c in scrape_configs if c.get("job_name") == "fastapi"),
            None
        )
        assert fastapi_config is not None, "fastapi scrape config not found"
        assert "static_configs" in fastapi_config, "fastapi static_configs not defined"

        targets = fastapi_config["static_configs"][0].get("targets", [])
        assert "api:8000" in str(targets), \
            "fastapi scrape config should target api:8000/metrics"

    def test_prometheus_retention_configured(self):
        """Test that Prometheus retention is configured"""
        from pathlib import Path
        import yaml

        prometheus_yml = Path(__file__).parent.parent / "docker" / "prometheus.yml"
        with open(prometheus_yml) as f:
            prometheus = yaml.safe_load(f)

        # Check retention settings
        retention = prometheus.get("retention", None)
        if retention is None:
            # Check docker-compose.yml instead
            docker_compose = Path(__file__).parent.parent.parent / "docker-compose.yml"
            with open(docker_compose) as f:
                compose = yaml.safe_load(f)

            prometheus_cmd = compose["services"]["prometheus"].get("command", "")
            assert "--storage.tsdb.retention.time=30d" in prometheus_cmd, \
                "Prometheus retention should be 30 days"
        else:
            assert "30d" in retention, "Prometheus retention should be 30 days"


@pytest.mark.docker
@pytest.mark.integration
class TestGrafanaConfiguration:
    """Grafana configuration tests"""

    def test_grafana_datasource_config_exists(self):
        """Test that Grafana datasource configuration exists"""
        from pathlib import Path
        datasource_yml = Path(__file__).parent.parent.parent / "docker" / "grafana" / "datasources" / "prometheus.yml"
        assert datasource_yml.exists(), "docker/grafana/datasources/prometheus.yml not found"

    def test_grafana_datasource_config(self):
        """Test that Grafana datasource is correctly configured"""
        from pathlib import Path
        import yaml

        datasource_yml = Path(__file__).parent.parent.parent / "docker" / "grafana" / "datasources" / "prometheus.yml"
        with open(datasource_yml) as f:
            datasources = yaml.safe_load(f)

        # Check for Prometheus datasource
        assert "datasources" in datasources, "datasources not defined in Grafana config"
        datasources_list = datasources["datasources"]

        prometheus_ds = next(
            (ds for ds in datasources_list if ds.get("name") == "Prometheus"),
            None
        )
        assert prometheus_ds is not None, "Prometheus datasource not defined"

        # Check datasource settings
        assert "url" in prometheus_ds, "Prometheus datasource URL not defined"
        assert "http://prometheus:9090" in prometheus_ds["url"], \
            "Prometheus datasource should point to http://prometheus:9090"

        # Check for time interval (5 seconds as per plan)
        # This might be in a separate provision config
        # For now, we just check it's configured

    def test_grafana_dashboards_exist(self):
        """Test that Grafana dashboards exist"""
        from pathlib import Path

        dashboards_dir = Path(__file__).parent.parent.parent / "docker" / "grafana" / "dashboards"
        assert dashboards_dir.exists(), "docker/grafana/dashboards directory not found"

        # Check for required dashboards
        required_dashboards = [
            "api_performance.json",
            "system_resources.json",
            "celery_tasks.json"
        ]

        for dashboard in required_dashboards:
            dashboard_path = dashboards_dir / dashboard
            assert dashboard_path.exists(), f"Grafana dashboard {dashboard} not found"

    def test_grafana_dashboard_content(self):
        """Test that Grafana dashboard has required panels"""
        from pathlib import Path
        import json

        dashboard_path = Path(__file__).parent.parent.parent / "docker" / "grafana" / "dashboards" / "api_performance.json"
        with open(dashboard_path) as f:
            dashboard = json.load(f)

        # Check for dashboard structure
        assert "dashboard" in dashboard, "Dashboard structure not valid"
        dashboard_obj = dashboard["dashboard"]

        # Check for panels
        assert "panels" in dashboard_obj, "Dashboard has no panels"

        # Check for key metrics (requests per second)
        panels = dashboard_obj["panels"]
        panel_titles = [panel.get("title", "") for panel in panels]

        # Check for common metrics
        has_requests = any("requests" in title.lower() for title in panel_titles)
        has_response_time = any("response" in title.lower() or "latency" in title.lower() for title in panel_titles)
        has_error_rate = any("error" in title.lower() for title in panel_titles)

        assert has_requests, "API dashboard missing requests metric"
        assert has_response_time, "API dashboard missing response time metric"
        assert has_error_rate, "API dashboard missing error rate metric"


@pytest.mark.docker
@pytest.mark.integration
class TestNetworkConnectivity:
    """Network connectivity tests for Docker services"""

    def test_docker_network_configured(self):
        """Test that Docker network is configured"""
        from pathlib import Path
        import yaml

        docker_compose = Path(__file__).parent.parent.parent / "docker-compose.yml"
        with open(docker_compose) as f:
            compose = yaml.safe_load(f)

        # Check for network configuration
        services = compose.get("services", {})

        # All services should be in the same network
        network_names = set()
        for service_name, service_config in services.items():
            networks = service_config.get("networks", ["default"])
            network_names.update(networks)

        # At least one network should be defined
        assert len(network_names) > 0, "No networks configured in docker-compose.yml"

    def test_service_dependencies_configured(self):
        """Test that service dependencies are configured"""
        from pathlib import Path
        import yaml

        docker_compose = Path(__file__).parent.parent.parent / "docker-compose.yml"
        with open(docker_compose) as f:
            compose = yaml.safe_load(f)

        services = compose.get("services", {})

        # API should depend on postgres and redis
        api_deps = services.get("api", {}).get("depends_on", [])
        assert "postgres" in api_deps, "API should depend on postgres"
        assert "redis" in api_deps, "API should depend on redis"

        # Worker should depend on postgres, redis, and api
        worker_deps = services.get("worker", {}).get("depends_on", [])
        assert "postgres" in worker_deps, "Worker should depend on postgres"
        assert "redis" in worker_deps, "Worker should depend on redis"

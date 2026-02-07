"""
Locust load testing file for FFmpeg API

Simulates realistic user behavior with two user types:
1. FFmpegAPIUser - Regular user viewing content (get_tasks@3, get_files@2, get_user_stats@1)
2. CreateTaskUser - User creating processing tasks (create_join_task, create_audio_overlay_task)
"""
import os
import random
import time
from datetime import timedelta
from io import BytesIO
from pathlib import Path

import gevent
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner


# Configuration
BASE_URL = os.environ.get("LOCUST_BASE_URL", "http://localhost:8000")
API_PREFIX = "/api/v1"

# Test data
TEST_USERNAME = f"loadtest_{random.randint(1000, 9999)}"
TEST_EMAIL = f"{TEST_USERNAME}@loadtest.com"
TEST_PASSWORD = "LoadTest123!"


class FFmpegAPIUser(HttpUser):
    """
    Simulates a regular user viewing content.
    Weighted tasks: get_tasks (3), get_files (2), get_user_stats (1)
    """
    
    # Wait between 1-3 seconds between tasks
    wait_time = between(1, 3)
    
    def on_start(self):
        """
        Authenticate on start.
        Create user if needed and obtain JWT token.
        """
        self.user_data = {
            "username": f"loadtest_{random.randint(1000, 9999)}",
            "email": f"loadtest_{random.randint(1000, 9999)}@test.com",
            "password": TEST_PASSWORD
        }
        
        # Try to login first, register if fails
        self.token = self._authenticate()
        if not self.token:
            self._register()
            self.token = self._authenticate()
        
        if not self.token:
            self.environment.runner.quit()
            return
        
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        # Upload some test files for the user
        self.file_ids = []
        for _ in range(2):
            file_id = self._upload_test_file()
            if file_id:
                self.file_ids.append(file_id)
    
    def _authenticate(self):
        """Attempt to login and return access token."""
        try:
            response = self.client.post(
                f"{API_PREFIX}/auth/login",
                data={
                    "username": self.user_data["username"],
                    "password": self.user_data["password"]
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("access_token")
        except Exception:
            pass
        return None
    
    def _register(self):
        """Register a new user."""
        self.client.post(
            f"{API_PREFIX}/auth/register",
            json={
                "username": self.user_data["username"],
                "email": self.user_data["email"],
                "password": self.user_data["password"]
            },
            headers={"Content-Type": "application/json"}
        )
    
    def _upload_test_file(self):
        """
        Upload a small test video file.
        Returns file ID if successful, None otherwise.
        """
        # Create a minimal test video (1MB of dummy data)
        test_file_path = Path(__file__).parent.parent / "fixtures" / "test_video.mp4"
        
        try:
            if test_file_path.exists():
                with open(test_file_path, "rb") as f:
                    file_content = f.read()
            else:
                # Fallback: create dummy video data
                file_content = b"FAV" + bytes(1024 * 1024)  # ~1MB dummy file
            
            response = self.client.post(
                f"{API_PREFIX}/files/upload",
                files={
                    "file": (f"test_video_{random.randint(1, 1000)}.mp4", file_content, "video/mp4")
                },
                headers={"Authorization": f"Bearer {self.token}"}
            )
            
            if response.status_code == 201:
                return response.json().get("id")
        except Exception:
            pass
        
        return None
    
    @task(3)
    def get_tasks(self):
        """
        Get list of user's tasks with pagination.
        Simulates browsing through task history.
        """
        with self.client.get(
            f"{API_PREFIX}/tasks",
            headers=self.headers,
            name="/api/v1/tasks",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:
                response.failure("Unauthorized - token expired")
                # Try to re-authenticate
                self.token = self._authenticate()
                if self.token:
                    self.headers["Authorization"] = f"Bearer {self.token}"
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(2)
    def get_files(self):
        """
        Get list of user's files.
        Simulates browsing uploaded files.
        """
        with self.client.get(
            f"{API_PREFIX}/files",
            headers=self.headers,
            name="/api/v1/files",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:
                response.failure("Unauthorized - token expired")
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(1)
    def get_user_stats(self):
        """
        Get user statistics.
        Simulates checking account overview.
        """
        with self.client.get(
            f"{API_PREFIX}/users/me/stats",
            headers=self.headers,
            name="/api/v1/users/me/stats",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:
                response.failure("Unauthorized - token expired")
            else:
                response.failure(f"Unexpected status: {response.status_code}")


class CreateTaskUser(HttpUser):
    """
    Simulates a user creating and processing tasks.
    Tasks: create_join_task, create_audio_overlay_task
    
    Note: Requires at least 2 video files for join tasks
    """
    
    # Wait between 2-5 seconds between tasks
    wait_time = between(2, 5)
    
    def on_start(self):
        """
        Authenticate and upload test files needed for task creation.
        """
        self.user_data = {
            "username": f"createtask_{random.randint(1000, 9999)}",
            "email": f"createtask_{random.randint(1000, 9999)}@test.com",
            "password": TEST_PASSWORD
        }
        
        # Register and login
        self._register()
        self.token = self._authenticate()
        
        if not self.token:
            self.environment.runner.quit()
            return
        
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        # Upload test files (need at least 2 for join task, 1 video + 1 audio for audio overlay)
        self.file_ids = []
        self.audio_file_ids = []
        
        # Upload 3 video files
        for _ in range(3):
            file_id = self._upload_test_file("video")
            if file_id:
                self.file_ids.append(file_id)
        
        # Upload 1 audio file
        audio_id = self._upload_test_file("audio")
        if audio_id:
            self.audio_file_ids.append(audio_id)
    
    def _authenticate(self):
        """Login and return access token."""
        try:
            response = self.client.post(
                f"{API_PREFIX}/auth/login",
                data={
                    "username": self.user_data["username"],
                    "password": self.user_data["password"]
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("access_token")
        except Exception:
            pass
        return None
    
    def _register(self):
        """Register a new user."""
        self.client.post(
            f"{API_PREFIX}/auth/register",
            json={
                "username": self.user_data["username"],
                "email": self.user_data["email"],
                "password": self.user_data["password"]
            },
            headers={"Content-Type": "application/json"}
        )
    
    def _upload_test_file(self, file_type="video"):
        """
        Upload a test file (video or audio).
        Returns file ID if successful.
        """
        test_video_path = Path(__file__).parent.parent / "fixtures" / "test_video.mp4"
        test_audio_path = Path(__file__).parent.parent / "fixtures" / "test_audio.mp3"
        
        try:
            if file_type == "video" and test_video_path.exists():
                with open(test_video_path, "rb") as f:
                    file_content = f.read()
                content_type = "video/mp4"
                filename = f"video_{random.randint(1, 1000)}.mp4"
            elif file_type == "audio" and test_audio_path.exists():
                with open(test_audio_path, "rb") as f:
                    file_content = f.read()
                content_type = "audio/mpeg"
                filename = f"audio_{random.randint(1, 1000)}.mp3"
            else:
                # Fallback: create dummy data
                file_content = b"FAV" + bytes(1024 * 1024)  # ~1MB
                content_type = "video/mp4" if file_type == "video" else "audio/mpeg"
                filename = f"test_{file_type}_{random.randint(1, 1000)}.mp4"
            
            response = self.client.post(
                f"{API_PREFIX}/files/upload",
                files={
                    "file": (filename, file_content, content_type)
                },
                headers={"Authorization": f"Bearer {self.token}"}
            )
            
            if response.status_code == 201:
                return response.json().get("id")
        except Exception:
            pass
        
        return None
    
    @task
    def create_join_task(self):
        """
        Create a video join task.
        Requires at least 2 video files.
        """
        if len(self.file_ids) < 2:
            return
        
        # Randomly select 2 video files
        selected_files = random.sample(self.file_ids, 2)
        
        with self.client.post(
            f"{API_PREFIX}/tasks/join",
            json={
                "file_ids": selected_files,
                "output_filename": f"joined_{random.randint(1, 10000)}.mp4"
            },
            headers=self.headers,
            name="/api/v1/tasks/join",
            catch_response=True
        ) as response:
            if response.status_code == 201:
                response.success()
            elif response.status_code == 400:
                response.failure("Bad request - validation error")
            elif response.status_code == 404:
                response.failure("Files not found")
            elif response.status_code == 401:
                response.failure("Unauthorized")
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task
    def create_audio_overlay_task(self):
        """
        Create an audio overlay task.
        Requires 1 video file and 1 audio file.
        """
        if not self.file_ids or not self.audio_file_ids:
            return
        
        video_file = random.choice(self.file_ids)
        audio_file = random.choice(self.audio_file_ids)
        
        with self.client.post(
            f"{API_PREFIX}/tasks/audio-overlay",
            json={
                "video_file_id": video_file,
                "audio_file_id": audio_file,
                "mode": "mix",
                "offset": 0.0,
                "overlay_volume": 1.0,
                "original_volume": 0.5
            },
            headers=self.headers,
            name="/api/v1/tasks/audio-overlay",
            catch_response=True
        ) as response:
            if response.status_code == 201:
                response.success()
            elif response.status_code == 400:
                response.failure("Bad request - validation error")
            elif response.status_code == 404:
                response.failure("Files not found")
            elif response.status_code == 401:
                response.failure("Unauthorized")
            else:
                response.failure(f"Unexpected status: {response.status_code}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """
    Print summary statistics and optimization recommendations when test stops.
    """
    if environment.runner is None:
        return
    
    print("\n" + "=" * 80)
    print("LOAD TEST SUMMARY")
    print("=" * 80)
    
    stats = environment.runner.stats
    if stats.total.num_requests > 0:
        print(f"\nTotal Requests: {stats.total.num_requests}")
        print(f"Total Failures: {stats.total.num_failures}")
        print(f"Failure Rate: {stats.total.fail_ratio * 100:.2f}%")
        print(f"Total RPS: {stats.total.total_rps:.2f}")
        
        # Response time statistics
        print(f"\nResponse Time Statistics:")
        print(f"  Min: {stats.total.min_response_time:.2f} ms")
        print(f"  Average: {stats.total.avg_response_time:.2f} ms")
        print(f"  Median (p50): {stats.total.get_response_time_percentile(0.5):.2f} ms")
        print(f"  p95: {stats.total.get_response_time_percentile(0.95):.2f} ms")
        print(f"  p99: {stats.total.get_response_time_percentile(0.99):.2f} ms")
        print(f"  Max: {stats.total.max_response_time:.2f} ms")
        
        # Check against targets
        print("\n" + "-" * 80)
        print("TARGET ANALYSIS")
        print("-" * 80)
        
        targets_met = True
        
        # Check failure rate
        if stats.total.fail_ratio * 100 > 5:
            print(f"❌ Failure rate ({stats.total.fail_ratio * 100:.2f}%) exceeds target (< 5%)")
            targets_met = False
        else:
            print(f"✓ Failure rate ({stats.total.fail_ratio * 100:.2f}%) meets target (< 5%)")
        
        # Check p95 response time
        p95 = stats.total.get_response_time_percentile(0.95)
        if p95 > 500:
            print(f"❌ p95 response time ({p95:.2f} ms) exceeds target (< 500ms)")
            targets_met = False
        else:
            print(f"✓ p95 response time ({p95:.2f} ms) meets target (< 500ms)")
        
        # Check p99 response time
        p99 = stats.total.get_response_time_percentile(0.99)
        if p99 > 1000:
            print(f"❌ p99 response time ({p99:.2f} ms) exceeds target (< 1000ms)")
            targets_met = False
        else:
            print(f"✓ p99 response time ({p99:.2f} ms) meets target (< 1000ms)")
        
        # Print recommendations
        print("\n" + "-" * 80)
        print("OPTIMIZATION RECOMMENDATIONS")
        print("-" * 80)
        
        if stats.total.fail_ratio * 100 > 5:
            print("• High failure rate detected. Check:")
            print("  - Database connection pool size")
            print("  - Redis connection stability")
            print("  - MinIO storage availability")
            print("  - API rate limiting configuration")
        
        if p95 > 500 or p99 > 1000:
            print("• Slow response times detected. Consider:")
            print("  - Adding caching layer for frequently accessed data")
            print("  - Optimizing database queries with proper indexes")
            print("  - Implementing read replicas for PostgreSQL")
            print("  - Scaling horizontally with multiple API instances")
            print("  - Using connection pooling for database/Redis")
        
        if stats.total.total_rps < 100:
            print("• Low throughput detected. Consider:")
            print("  - Increasing worker processes")
            print("  - Using async operations where possible")
            print("  - Implementing request batching")
            print("  - Reducing unnecessary middleware")
        else:
            print("✓ Good throughput achieved")
        
        # Endpoint-specific analysis
        print("\n" + "-" * 80)
        print("ENDPOINT ANALYSIS")
        print("-" * 80)
        
        for name, stat in stats.entries.items():
            if stat.num_requests > 0:
                failure_rate = (stat.num_failures / stat.num_requests) * 100
                print(f"\n{name}:")
                print(f"  Requests: {stat.num_requests}")
                print(f"  Failures: {stat.num_failures} ({failure_rate:.2f}%)")
                print(f"  Avg Response: {stat.avg_response_time:.2f} ms")
                print(f"  p95: {stat.get_response_time_percentile(0.95):.2f} ms")
                
                if failure_rate > 10:
                    print(f"  ⚠️  High failure rate - investigate this endpoint")
                elif stat.avg_response_time > 1000:
                    print(f"  ⚠️  Slow response time - consider optimization")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETED")
    print("=" * 80 + "\n")

"""
Integration tests for MinIO
"""
import pytest
import io
from datetime import timedelta
from minio import Minio
from minio.error import S3Error


@pytest.mark.integration
@pytest.mark.requires_network
class TestMinIOIntegration:
    """Integration tests for MinIO"""

    @pytest.fixture
    async def minio_client(self):
        """Create MinIO client for testing"""
        client = Minio(
            "localhost:9000",
            access_key="minioadmin",
            secret_key="minioadmin",
            secure=False
        )

        # Create test bucket
        bucket_name = "test-bucket"
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)

        yield client

        # Cleanup: remove all objects and bucket
        try:
            objects = client.list_objects(bucket_name, recursive=True)
            for obj in objects:
                client.remove_object(bucket_name, obj.object_name)
            client.remove_bucket(bucket_name)
        except S3Error:
            pass  # Bucket might already be deleted

    @pytest.mark.asyncio
    async def test_create_bucket(self, minio_client):
        """Test creating a bucket"""
        bucket_name = "test-create-bucket"

        # Create bucket
        minio_client.make_bucket(bucket_name)

        # Verify bucket exists
        assert minio_client.bucket_exists(bucket_name) is True

        # Cleanup
        minio_client.remove_bucket(bucket_name)

    @pytest.mark.asyncio
    async def test_bucket_exists(self, minio_client):
        """Test checking if bucket exists"""
        assert minio_client.bucket_exists("test-bucket") is True
        assert minio_client.bucket_exists("nonexistent-bucket") is False

    @pytest.mark.asyncio
    async def test_upload_file(self, minio_client):
        """Test uploading a file"""
        file_content = b"test content" * 100
        minio_client.put_object(
            "test-bucket",
            "test.txt",
            io.BytesIO(file_content),
            length=len(file_content)
        )

        # Check that file was uploaded
        objects = list(minio_client.list_objects("test-bucket"))
        assert len(objects) == 1
        assert objects[0].object_name == "test.txt"
        assert objects[0].size == len(file_content)

    @pytest.mark.asyncio
    async def test_download_file(self, minio_client):
        """Test downloading a file"""
        file_content = b"download test" * 100

        # Upload file
        minio_client.put_object(
            "test-bucket",
            "download.txt",
            io.BytesIO(file_content),
            length=len(file_content)
        )

        # Download file
        data = minio_client.get_object("test-bucket", "download.txt")
        downloaded = data.read()

        assert downloaded == file_content

    @pytest.mark.asyncio
    async def test_delete_file(self, minio_client):
        """Test deleting a file"""
        # Upload file
        minio_client.put_object(
            "test-bucket",
            "delete.txt",
            io.BytesIO(b"delete me"),
            length=9
        )

        # Delete file
        minio_client.remove_object("test-bucket", "delete.txt")

        # Verify deletion
        objects = list(minio_client.list_objects("test-bucket"))
        assert not any(obj.object_name == "delete.txt" for obj in objects)

    @pytest.mark.asyncio
    async def test_list_files(self, minio_client):
        """Test listing files in bucket"""
        # Upload multiple files
        for i in range(5):
            minio_client.put_object(
                "test-bucket",
                f"file{i}.txt",
                io.BytesIO(f"content{i}".encode()),
                length=len(f"content{i}".encode())
            )

        # List files
        objects = list(minio_client.list_objects("test-bucket"))
        assert len(objects) == 5

    @pytest.mark.asyncio
    async def test_list_files_with_prefix(self, minio_client):
        """Test listing files with prefix"""
        # Upload files with different prefixes
        minio_client.put_object(
            "test-bucket",
            "videos/video1.mp4",
            io.BytesIO(b"video"),
            length=5
        )
        minio_client.put_object(
            "test-bucket",
            "videos/video2.mp4",
            io.BytesIO(b"video"),
            length=5
        )
        minio_client.put_object(
            "test-bucket",
            "images/image1.jpg",
            io.BytesIO(b"image"),
            length=5
        )

        # List files with prefix
        videos = list(minio_client.list_objects("test-bucket", prefix="videos/"))
        assert len(videos) == 2
        assert all(obj.object_name.startswith("videos/") for obj in videos)

    @pytest.mark.asyncio
    async def test_generate_presigned_url(self, minio_client):
        """Test generating presigned URL"""
        file_content = b"presigned test"

        # Upload file
        minio_client.put_object(
            "test-bucket",
            "presigned.txt",
            io.BytesIO(file_content),
            length=len(file_content)
        )

        # Generate URL
        url = minio_client.presigned_get_object(
            "test-bucket",
            "presigned.txt",
            expires=timedelta(hours=1)
        )

        assert "localhost:9000" in url
        assert "presigned.txt" in url
        assert "X-Amz-" in url  # AWS signature

    @pytest.mark.asyncio
    async def test_file_metadata(self, minio_client):
        """Test file metadata"""
        file_content = b"metadata test"

        # Upload file with metadata
        minio_client.put_object(
            "test-bucket",
            "metadata.txt",
            io.BytesIO(file_content),
            length=len(file_content),
            metadata={
                "Content-Type": "text/plain",
                "Custom-Header": "Custom-Value"
            }
        )

        # Get file stat
        stat = minio_client.stat_object("test-bucket", "metadata.txt")

        assert stat.size == len(file_content)
        assert stat.content_type == "text/plain"
        assert "Custom-Header" in stat.metadata

    @pytest.mark.asyncio
    async def test_copy_file(self, minio_client):
        """Test copying a file"""
        file_content = b"copy test"

        # Upload source file
        minio_client.put_object(
            "test-bucket",
            "source.txt",
            io.BytesIO(file_content),
            length=len(file_content)
        )

        # Copy file
        minio_client.copy_object(
            "test-bucket",
            "destination.txt",
            "test-bucket/source.txt"
        )

        # Verify copy
        source_stat = minio_client.stat_object("test-bucket", "source.txt")
        dest_stat = minio_client.stat_object("test-bucket", "destination.txt")

        assert source_stat.size == dest_stat.size
        assert source_stat.etag == dest_stat.etag

    @pytest.mark.asyncio
    async def test_remove_objects_batch(self, minio_client):
        """Test removing multiple objects"""
        # Upload multiple files
        object_names = [f"batch{i}.txt" for i in range(10)]
        for name in object_names:
            minio_client.put_object(
                "test-bucket",
                name,
                io.BytesIO(b"content"),
                length=7
            )

        # Remove all objects
        for name in object_names:
            minio_client.remove_object("test-bucket", name)

        # Verify all removed
        objects = list(minio_client.list_objects("test-bucket"))
        assert len(objects) == 0

import os
import uuid
from werkzeug.utils import secure_filename
from config import Config

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class StorageService:
    @staticmethod
    def save_parcel_photo(file_storage):
        """
        Stores unstructured parcel photos.
        Uses Azure Blob Storage if configured, or falls back to local uploads directory.
        Returns the accessible URL or path of the uploaded photo.
        """
        if not file_storage or file_storage.filename == '':
            return None

        if not allowed_file(file_storage.filename):
            raise ValueError("Unsupported file type. Only image files (PNG, JPG, JPEG, WEBP) are allowed.")

        # Sanitize filename and prepend unique uuid for collision prevention
        original_name = secure_filename(file_storage.filename)
        unique_name = f"{uuid.uuid4().hex[:12]}_{original_name}"

        # 1. Try Azure Blob Storage (Cloud Unstructured Storage - DP-900)
        if Config.AZURE_STORAGE_CONNECTION_STRING:
            try:
                from azure.storage.blob import BlobServiceClient
                blob_service = BlobServiceClient.from_connection_string(Config.AZURE_STORAGE_CONNECTION_STRING)
                container_client = blob_service.get_container_client(Config.AZURE_STORAGE_CONTAINER_NAME)
                
                # Ensure container exists
                if not container_client.exists():
                    container_client.create_container(public_access="blob")

                blob_client = container_client.get_blob_client(unique_name)
                blob_client.upload_blob(file_storage.stream, overwrite=True)
                return blob_client.url
            except Exception as e:
                # Log error and fall back to local disk
                print(f"[StorageService Warning] Azure Blob upload failed, falling back to local storage: {e}")

        # 2. Local Fallback Storage
        os.makedirs(Config.LOCAL_UPLOAD_FOLDER, exist_ok=True)
        local_path = os.path.join(Config.LOCAL_UPLOAD_FOLDER, unique_name)
        file_storage.save(local_path)
        return f"/static/uploads/{unique_name}"

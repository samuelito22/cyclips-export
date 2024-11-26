import os
from azure.storage.blob import BlobServiceClient
from urllib.parse import urlparse
import logging

logger = logging.getLogger("logger_name")
logger.disabled = True

def upload_file(destination_url: str, file_path: str):
    """
    Uploads a file to Azure Blob Storage using a destination URL.

    Args:
        destination_url (str): The URL of the blob in Azure Blob Storage.
        file_path (str): The local file path to upload.
    """
    azure_storage_key = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    
    if not azure_storage_key:
        raise ValueError("Environment variable 'AZURE_STORAGE_CONNECTION_STRING' is not set or empty.")
    
    try:
        parsed_url = urlparse(destination_url)
        path_segments = parsed_url.path.lstrip("/").split("/")
        container_name = path_segments[0]
        blob_name = "/".join(path_segments[1:])
        
        blob_service_client = BlobServiceClient.from_connection_string(azure_storage_key, logger=logger)

        try:
            container_client = blob_service_client.create_container(container_name)
            logger.info(f"Container '{container_name}' created.")
        except Exception as e:
            logger.warning(f"Container creation failed or already exists: {e}")
        
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)

        with open(file_path, "rb") as data:
            blob_client.upload_blob(data=data, blob_type="BlockBlob", overwrite=True, max_concurrency=5, connection_timeout=600)
        
        print(f"File uploaded successfully to {destination_url}")

    except Exception as e:
        logger.error(f"Failed to upload file to {destination_url}: {e}")
        raise

import os
import sys
import logging
import subprocess
import jenkins
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from azure.storage.blob import BlobServiceClient, generate_account_sas, ResourceTypes, AccountSasPermissions
import uuid
import requests
import json
from jenkins_helper import rename_file_uuid, setup_logging, get_secret



def get_file_metadata(file_name, file_path):
    """
    Get metadata of the file.
    
    Args:
        file_path: Path to the file
    
    Returns:
        dict: Metadata of the file
    """
    
    metadata = {
        'id': os.path.splitext(os.path.basename(file_path))[0],
        'packagemode': get_secret('PACKAGE_MODE'),
        'packagename': file_name,
        'commit': get_secret('COMMIT_SHA'),
        'packageformat': os.path.splitext(os.path.basename(file_path))[1],
        'packagesize': os.path.getsize(file_path)
    }
    return metadata


def register_file_to_newdahkobed(package_name, file_path):
    """
    Register the uploaded file to newdahkobed
    Get all the required data about the file
    
    Args:
        file_path: Path to the file that was uploaded
    """
    
    try:
        # Get metadata about the file

        metadata = get_file_metadata(package_name, file_path)
        
        # Get Cosmos DB endpoint and key from secrets
        cosmos_endpoint = get_secret('SERVER_ENDPOINT')
        
        # Make POST request to register the file
        logger.info(f"Registering file metadata to newdahkobed: {metadata['id']}")
        
        header = {
            'Content-Type': 'application/json'
        }
        
        response = requests.post(cosmos_endpoint + "/submit", headers=header, params=metadata )
        
        # Check response status
        if response.status_code in (200, 201, 204):
            logger.info(f"Successfully registered file in newdahkobed. Status code: {response.status_code}")
            return True
        else:
            logger.error(f"Failed to register file in newdahkobed. Status code: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error registering file to newdahkobed: {str(e)}")
        return False    
    
    


def upload_file_with_azcopy(file_path):
    """
    Upload a file to Azure Storage using azcopy.
    
    Args:
        file_path: Path to the file that should be uploaded
    
    Returns:
        bool: True if upload was successful, False otherwise
    """
    try:
       
        if not os.path.isabs(file_path):
            file_path = os.path.join(os.getcwd(), file_path)
        # Remove leading slash if it's just a relative path mistakenly starting with /
        elif file_path.startswith('/') and not os.path.exists(file_path) and os.path.exists(file_path[1:]):
            file_path = file_path[1:]
            logger.info(f"Looking for file at path: {file_path}")
            
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            # Try to list files in the directory to help debug
            try:
                dir_path = os.path.dirname(file_path) or '.'
                logger.info(f"Contents of directory {dir_path}: {os.listdir(dir_path)}")
            except Exception as dir_err:
                logger.error(f"Could not list directory contents: {str(dir_err)}")
            return False
        
        # Get required Azure credentials
        storage_account = get_secret('AZURE_STORAGE_ACCOUNT')
        storage_key = get_secret('AZURE_STORAGE_KEY')
        #TODO Update this to build mode
        container_name = get_secret('AZURE_CONTAINER_NAME')
        
        
        
        # Generate SAS token for azcopy (in real implementation, you might want to use a helper function)
        # For this example, we'll assume the SAS token is stored directly
        sas_token = generate_account_sas(
            storage_account,
            storage_key,
            resource_types=ResourceTypes(container=True, object=True),
            permission=AccountSasPermissions(write=True,read=True, add=True, create=True),
            expiry=datetime.now(timezone.utc) + timedelta(hours=1)
        )
        
        package_name = os.path.basename(file_path)
        logger.info(f"Package Name: {package_name}")
        rename_path = rename_file_uuid(file_path)
        logger.info(f"Renamed file to {rename_path}")
        
        file_name = os.path.basename(rename_path)
        # Build the destination URL
        destination_url = f"https://{storage_account}.blob.core.windows.net/{container_name}/{file_name}?{sas_token}"
        
        
        # Check if container exists and create it if it doesn't
        blob_service_client = BlobServiceClient(
            account_url=f"https://{storage_account}.blob.core.windows.net",
            credential=storage_key
        )
        try:
            # Try to get the container client
            container_client = blob_service_client.get_container_client(container_name)
            
            # Check if container exists
            if not container_client.exists():
                logger.info(f"Container {container_name} does not exist. Creating now...")
                container_client.create_container()
                logger.info(f"Container {container_name} created successfully")
            else:
                logger.info(f"Container {container_name} already exists")
        except Exception as e:
            logger.error(f"Error checking/creating container: {str(e)}")
            return False
        
        logger.info(f"Uploading {rename_path} to Azure Storage")
        
        # Execute azcopy command
        cmd = ['azcopy', 'copy', rename_path, destination_url, '--overwrite=true']
        result = subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr, text=True)

        if result.returncode == 0:
            logger.info(f"Successfully uploaded {file_path} to Azure Storage")
            register_file_to_newdahkobed(package_name, rename_path)
            return True
        else:
            logger.error({result})
            logger.error(f"Failed to upload file: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        return False


# Main execution
if __name__ == "__main__":
    
    # Configure logging for Jenkins console output
    logger = logging.getLogger('package-uploader')
    
    # Only load .env file if not running in Jenkins environment
    if not os.getenv('JENKINS_HOME'):
        logger.info("Not detected in Jenkins environment, loading secrets from .env file")
        load_dotenv()
    else:
        logger.info("Running in Jenkins environment")

    # Check if the server is healthy before proceeding
    try:
        server_endpoint = get_secret('SERVER_ENDPOINT')
        logger.info(f"Checking server health at {server_endpoint}/healthcheck")
        health_response = requests.get(f"{server_endpoint}/healthcheck", timeout=10)
        
        if health_response.status_code == 200 and health_response.text == 'Alive':
            logger.info("Server health check passed")
        else:
            logger.error(f"Server health check failed with status code: {health_response.status_code}")
            logger.error(f"Response: {health_response.text}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to perform server health check: {str(e)}")
        sys.exit(1)
    #SERVER UP AND RUNNING - Attempt to upload the file
    try:
        upload_file_with_azcopy(get_secret('TEST_FILE'))
        
    except Exception as e:
        logger.error(f"Script failed: {str(e)}")
        sys.exit(1)
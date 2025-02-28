import os
import sys
import logging
import subprocess
import jenkins
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions

def generate_azure_sas_token(storage_account, storage_key, container_name, blob_name=None, expiry_hours=1):
    """
    Generate an Azure SAS token for blob storage access.
    
    Args:
        storage_account: Azure storage account name
        storage_key: Azure storage account key
        container_name: Container name
        blob_name: Optional - specific blob name (if None, applies to whole container)
        expiry_hours: Number of hours the token should be valid for
        
    Returns:
        str: SAS token string (includes the '?' prefix for appending to URLs)
    """
    try:
        # Calculate token start and expiry times
        start_time = datetime.utcnow()
        expiry_time = start_time + timedelta(hours=expiry_hours)
        
        # Define permissions
        permissions = BlobSasPermissions(
            read=True,       # Allow read operations
            write=True,      # Allow write operations 
            delete=False,    # Don't allow delete operations
            list=False,      # Don't allow listing blobs in container
            create=True      # Allow creating new blobs
        )
        
        # Generate the SAS token
        if blob_name:
            # Generate SAS for specific blob
            sas_token = generate_blob_sas(
                account_name=storage_account,
                container_name=container_name,
                blob_name=blob_name,
                account_key=storage_key,
                permission=permissions,
                expiry=expiry_time,
                start=start_time,
                protocol="https"
            )
        else:
            # Generate SAS for entire container
            sas_token = generate_blob_sas(
                account_name=storage_account,
                container_name=container_name,
                account_key=storage_key,
                permission=permissions,
                expiry=expiry_time,
                start=start_time,
                protocol="https"
            )
            
        # Return the SAS token with ? prefix for URL appending
        return f"?{sas_token}"
        
    except Exception as e:
        logger.error(f"Error generating SAS token: {str(e)}")
        return None
    
def get_secret(key):
    # For Jenkins jobs, first check if the secret is directly available as an environment variable
    # This is common when using Jenkins credentials binding plugin
    secret = os.getenv(key)
    if secret:
        logger.info(f"Found secret {key} in environment variables")
        return secret

    # If we're in Jenkins but the secret isn't directly bound, try to get it from Jenkins credentials
    if os.getenv('JENKINS_HOME'):
        try:
            # These should be provided by Jenkins when setting up the job
            jenkins_url = os.getenv('JENKINS_URL')
            jenkins_user = os.getenv('JENKINS_USER')
            jenkins_token = os.getenv('JENKINS_TOKEN')

            if not all([jenkins_url, jenkins_user, jenkins_token]):
                logger.error("Jenkins credentials are not set in environment variables")
                sys.exit(1)

            logger.info(f"Attempting to retrieve {key} from Jenkins credentials")
            server = jenkins.Jenkins(jenkins_url, username=jenkins_user, password=jenkins_token)
            secret = server.get_credential(key)
            if not secret:
                logger.error(f"Secret {key} not found in Jenkins credentials provider")
                sys.exit(1)
            return secret
            
        except Exception as e:
            logger.error(f"Error accessing Jenkins credentials: {str(e)}")
            sys.exit(1)
    
    # If we're not in Jenkins and the secret wasn't in environment variables
    logger.error(f"Secret {key} not found in any available sources")
    sys.exit(1)

def upload_file_with_azcopy(file_path):
    """
    Upload a file to Azure Storage using azcopy.
    
    Args:
        file_path: Path to the file that should be uploaded
    
    Returns:
        bool: True if upload was successful, False otherwise
    """
    try:
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return False
        
        # Get required Azure credentials
        storage_account = get_secret('AZURE_STORAGE_ACCOUNT')
        storage_key = get_secret('AZURE_STORAGE_KEY')
        #TODO Update this to build mode
        container_name = get_secret('AZURE_CONTAINER_NAME')
        client_id = get_secret('AZURE_CLIENT_ID')
        # Generate SAS token for azcopy (in real implementation, you might want to use a helper function)
        # For this example, we'll assume the SAS token is stored directly
        sas_token = generate_azure_sas_token(
            storage_account,
            storage_key,
            container_name,
            blob_name=os.path.basename(file_path),
            expiry_hours=1
        )
        
        # Build the destination URL
        file_name = os.path.basename(file_path)
        destination_url = f"https://{storage_account}.blob.core.windows.net/{container_name}/{file_name}{sas_token}"
        
        
        # azcopy loginazcopy login --identity --identity-client-id "<client-id>"
        cmd = ['azcopy', 'login', '--identity', '--identity-client-id', "${client_id}"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"Successfully logged in to AzCopy")
            logger.info(result.stdout)
        else:
            logger.error({result})
            logger.error(f"Failed to upload file: {result.stderr}")
            return False
        
        logger.info(f"Uploading {file_path} to Azure Storage")
        
        # Execute azcopy command
        cmd = ['azcopy', 'copy', file_path, destination_url, '--overwrite=true']
        result = subprocess.run(cmd, stdout=sys.stdout, stderr=sys.stderr, text=True)

        if result.returncode == 0:
            logger.info(f"Successfully uploaded {file_path} to Azure Storage")
            #register_file_to_cosmos(file_path)
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
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )   
    logger = logging.getLogger('package-uploader')

    # Only load .env file if not running in Jenkins environment
    if not os.getenv('JENKINS_HOME'):
        logger.info("Not detected in Jenkins environment, loading secrets from .env file")
        load_dotenv()
    else:
        logger.info("Running in Jenkins environment")

    try:
        # logger.info(f"Retrieving secret: {secret_key}")
        # secret_value = get_secret(secret_key)
        # logger.info(f"Successfully retrieved secret: {secret_key}")
        
        # # Instead of printing the actual secret value for security reasons
        # # just confirm it was retrieved successfully
        # logger.info(f"Secret {secret_key} was retrieved successfully")
        
        # Add your main application logic here that uses the secret
        
        upload_file_with_azcopy(get_secret('TEST_FILE'))
        
    except Exception as e:
        logger.error(f"Script failed: {str(e)}")
        sys.exit(1)
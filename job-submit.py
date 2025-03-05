import os
import sys
import logging
import subprocess
import jenkins
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import uuid
import requests
import json
from jenkins_helper import rename_file_uuid, setup_logging, get_secret

logger = logging.getLogger('jenkins-helper')

def upload_metadata_to_server(metadata, api_url=None):
    """
    Upload metadata to the server via API.
    
    Args:
        metadata: Dictionary containing the metadata to upload
        api_url: Optional API URL, otherwise will use API_URL from environment
        
    Returns:
        Server response as dictionary
        
    Raises:
        Exception: If upload fails
    """
    api_url = get_secret('JOB_SERVER_URL') or api_url
    
    if not api_url.endswith('/submit'):
        if not api_url.endswith('/'):
            api_url += '/'
        api_url += 'submit'
    
    logger.info(f"Uploading metadata to {api_url}")
    
    try:
        # Ensure metadata has required fields
        metadata['jobname'] = get_secret('JOB_NAME')
        metadata['jobnumber'] = get_secret('BUILD_NUMBER')
        metadata['id'] = str(uuid.uuid4())
            
        metadata['timestamp'] = datetime.now(timezone.utc).isoformat()
            
        response = requests.post(
            api_url,
            json=metadata,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to submit job record to server: {response.status_code} - {response.text}")
            raise Exception(f"Failed to submit job record to server: {response.status_code} - {response.text}")
            
        return response.json()
        
    except Exception as e:
        logger.error(f"Error recording job: {str(e)}")
        raise
        
        
def generate_build_metadata():
    """
    Generate build metadata from Jenkins environment variables.
    
    Returns:
        Dictionary containing build metadata
    """
    metadata = {
        'id': str(uuid.uuid4()),
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'jobname': get_secret('JOB_NAME'),
        'buildnumber': get_secret('BUILD_NUMBER'),
        'buildurl': get_secret('BUILD_URL'),
        'commit': get_secret('GIT_COMMIT'),
        'branch': get_secret('GIT_BRANCH'),
        'nodename': get_secret('NODE_NAME')
    }
    
    # Filter out empty values
    return {k: v for k, v in metadata.items() if v}


if __name__ == "__main__":
    # Only load .env file if not running in Jenkins environment
    if not os.getenv('JENKINS_HOME'):
        logger.info("Not detected in Jenkins environment, loading secrets from .env file")
        load_dotenv()
    else:
        logger.info("Running in Jenkins environment")

    # Check if the server is healthy before proceeding
    try:
        server_endpoint = get_secret('JOB_SERVER_URL')
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
        metadata = generate_build_metadata()
        if metadata:
            upload_metadata_to_server(metadata)
        else:
            logger.error("No metadata generated, skipping upload")
            raise Exception("No metadata generated, skipping upload")
        
    except Exception as e:
        logger.error(f"Script failed: {str(e)}")
        sys.exit(1)
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

# Configure logging
logger = logging.getLogger('jenkins-helper')

def rename_file_uuid(file_path):
    """
    Rename the file with a guid
    
    Args:
        file_path: Path to the file that should be renamed
    Returns:
        str: New file path with GUID name
    """
    
    # Generate a unique GUID
    guid = str(uuid.uuid4())
    
    # Get the file directory and extension
    file_dir = os.path.dirname(file_path)
    _, file_extension = os.path.splitext(file_path)
    
    # Create the new file path with GUID
    new_file_path = os.path.join(file_dir, guid + file_extension)
    
    # Rename the file
    os.rename(file_path, new_file_path)
    
    return new_file_path



def setup_logging(level=logging.INFO):
    """
    Set up logging configuration.
    
    Args:
        level: Logging level (default: INFO)
    
    Returns:
        Logger instance
    """
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    logger.setLevel(level)
    logger.addHandler(handler)
    
    return logger

def get_secret(key):
    """
    Get a secret from environment variables or Jenkins credentials.
    
    Args:
        key: The key/name of the secret to retrieve
    
    Returns:
        The secret value if found
        
    Raises:
        Exception: If the secret cannot be found
    """
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
                raise Exception("Jenkins credentials are not set in environment variables")

            logger.info(f"Attempting to retrieve {key} from Jenkins credentials")
            server = jenkins.Jenkins(jenkins_url, username=jenkins_user, password=jenkins_token)
            secret = server.get_credential(key)
            if not secret:
                secret = os.getenv(key)
                if not secret:
                    logger.error(f"Secret {key} not found in Jenkins credentials provider or environment variables")
                    raise Exception(f"Secret {key} not found in Jenkins credentials or environment variables")
            return secret
            
        except Exception as e:
            logger.error(f"Error accessing Jenkins credentials: {str(e)}")
            raise Exception(f"Error accessing Jenkins credentials: {str(e)}")
    
    # If we're not in Jenkins and the secret wasn't in environment variables
    # Try to load from .env file
    if os.path.exists('.env'):
        load_dotenv()
        secret = os.getenv(key)
        if secret:
            logger.info(f"Found secret {key} in .env file")
            return secret
    
    logger.error(f"Secret {key} not found in any available sources")
    raise Exception(f"Secret {key} not found in any available sources")



def run_command(command, capture_output=True, check=True):
    """
    Run a shell command and return its output.
    
    Args:
        command: Command to run (list or string)
        capture_output: Whether to capture command output
        check: Whether to check if command succeeded
        
    Returns:
        Command output if capture_output is True, otherwise None
        
    Raises:
        subprocess.CalledProcessError: If command fails and check is True
    """
    if isinstance(command, str):
        command = command.split()
        
    logger.info(f"Running command: {' '.join(command)}")
    
    try:
        result = subprocess.run(
            command,
            capture_output=capture_output,
            text=True,
            check=check
        )
        
        if capture_output:
            return result.stdout
        return None
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with exit code {e.returncode}")
        logger.error(f"Error output: {e.stderr}")
        raise

# Initialize logging when the module is imported
setup_logging()

# If this file is run directly, show usage information
if __name__ == "__main__":
    print("Jenkins Helper Module")
    print("This module provides helper functions for Jenkins scripts")
    print("Import this module in your Python scripts to use its functions")
    print("\nAvailable functions:")
    print("  - get_secret(key): Get a secret from environment or Jenkins")
    print("  - upload_metadata_to_server(metadata, api_url): Upload metadata to API")
    print("  - generate_build_metadata(): Generate metadata from Jenkins environment")
    print("  - run_command(command): Run a shell command")
    print("  - setup_logging(level): Configure logging")
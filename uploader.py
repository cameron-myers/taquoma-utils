import os
import sys
import logging
from dotenv import load_dotenv
import jenkins

# Configure logging for Jenkins console output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('package-uploader')

# Only load .env file if not running in Jenkins environment
if not os.getenv('JENKINS_HOME'):
    logger.info("Not detected in Jenkins environment, loading from .env file")
    load_dotenv()
else:
    logger.info("Running in Jenkins environment")

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

# Main execution
if __name__ == "__main__":
    try:
        secret_key = 'MY_SECRET_KEY'
        logger.info(f"Retrieving secret: {secret_key}")
        secret_value = get_secret(secret_key)
        logger.info(f"Successfully retrieved secret: {secret_key}")
        
        # Instead of printing the actual secret value for security reasons
        # just confirm it was retrieved successfully
        logger.info(f"Secret {secret_key} was retrieved successfully")
        
        # Add your main application logic here that uses the secret
        
    except Exception as e:
        logger.error(f"Script failed: {str(e)}")
        sys.exit(1)
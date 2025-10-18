"""
AWS Authentication Helper for Bedrock Integration

Implements authentication priority:
1. Bedrock API key (AWS_BEARER_TOKEN_BEDROCK)
2. AWS profile (AWS_PROFILE)
3. AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN)
"""
import boto3
import logging
from typing import Optional
from botocore.config import Config
from core.knowledgebase import constants

logger = logging.getLogger(__name__)
if not logger.handlers:
    # Avoid duplicate handlers in some runtimes
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


class AWSAuthenticator:
    """Handles AWS authentication with priority-based credential selection."""
    
    def __init__(self):
        self._session = None
        self._bedrock_client = None
        self._bedrock_runtime = None
        
    def get_bedrock_client(self):
        """Get authenticated Bedrock client for model management."""
        if self._bedrock_client is None:
            session = self.get_session()
            self._bedrock_client = session.client(
                'bedrock',
                region_name=constants.BEDROCK_REGION
            )
        return self._bedrock_client
    
    def get_bedrock_runtime_client(self):
        """Get authenticated Bedrock Runtime client for inference."""
        if self._bedrock_runtime is None:
            session = self.get_session()
            config = Config(
                read_timeout=300,  # Set a 5-minute read timeout
                connect_timeout=60,
                retries={'max_attempts': 3}
            )
            self._bedrock_runtime = session.client(
                'bedrock-runtime',
                region_name=constants.BEDROCK_REGION,
                config=config
            )
        return self._bedrock_runtime
    
    def get_session(self) -> boto3.Session:
        """Get authenticated boto3 session using priority-based authentication."""
        if self._session is not None:
            return self._session
            
        self._session = self._create_authenticated_session()
        return self._session
    
    def _create_authenticated_session(self) -> boto3.Session:
        """Create boto3 session with priority-based authentication."""
        
        # Priority 1: Bedrock API key (bearer token)
        if constants.AWS_BEARER_TOKEN_BEDROCK:
            logger.debug("Using Bedrock API key authentication")
            return self._create_session_with_bearer_token()
        
        # Priority 2: Named AWS profile
        elif constants.AWS_PROFILE:
            logger.debug(f"Using AWS profile: {constants.AWS_PROFILE}")
            return self._create_session_with_profile()
        
        # Priority 3: Explicit AWS credentials
        elif constants.AWS_ACCESS_KEY_ID and constants.AWS_SECRET_ACCESS_KEY:
            logger.debug("Using explicit AWS credentials")
            return self._create_session_with_credentials()
        
        # Fallback: Default AWS configuration
        else:
            logger.debug("Using default AWS configuration (environment/instance profile)")
            return boto3.Session(region_name=constants.BEDROCK_REGION)
    
    def _create_session_with_bearer_token(self) -> boto3.Session:
        """Create session using Bedrock API key (bearer token approach)."""
        # Note: Bearer tokens for Bedrock are typically used via API calls
        # For now, we'll create a session and handle bearer token in the actual API calls
        # This might need adjustment based on AWS Bedrock API key implementation
        return boto3.Session(region_name=constants.BEDROCK_REGION)
    
    def _create_session_with_profile(self) -> boto3.Session:
        """Create session using named AWS profile."""
        try:
            return boto3.Session(
                profile_name=constants.AWS_PROFILE,
                region_name=constants.BEDROCK_REGION
            )
        except Exception as e:
            logger.error(f"Failed to create session with profile {constants.AWS_PROFILE}: {e}")
            raise
    
    def _create_session_with_credentials(self) -> boto3.Session:
        """Create session using explicit AWS credentials."""
        try:
            return boto3.Session(
                aws_access_key_id=constants.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=constants.AWS_SECRET_ACCESS_KEY,
                aws_session_token=constants.AWS_SESSION_TOKEN,
                region_name=constants.BEDROCK_REGION
            )
        except Exception as e:
            logger.error(f"Failed to create session with explicit credentials: {e}")
            raise
    
    def test_authentication(self) -> bool:
        """Test if authentication is working by making a simple API call."""
        try:
            client = self.get_bedrock_client()
            # Test with a simple list models call
            response = client.list_foundation_models()
            logger.info("Authentication test successful")
            return True
        except Exception as e:
            logger.error(f"Authentication test failed: {e}")
            return False
    
    def get_auth_method(self) -> str:
        """Return string describing the authentication method being used."""
        if constants.AWS_BEARER_TOKEN_BEDROCK:
            return "Bedrock API Key"
        elif constants.AWS_PROFILE:
            return f"AWS Profile ({constants.AWS_PROFILE})"
        elif constants.AWS_ACCESS_KEY_ID and constants.AWS_SECRET_ACCESS_KEY:
            return "AWS Credentials"
        else:
            return "Default AWS Configuration"


# # Global authenticator instance
# _authenticator = None

# def get_authenticator() -> AWSAuthenticator:
#     """Get global AWS authenticator instance."""
#     global _authenticator
#     if _authenticator is None:
#         _authenticator = AWSAuthenticator()
#     return _authenticator
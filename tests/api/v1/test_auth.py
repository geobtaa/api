"""
Tests for the auth module.
"""

import os
from unittest.mock import patch

import pytest
from fastapi import HTTPException, status
from fastapi.security import HTTPBasicCredentials

from app.api.v1.auth import verify_credentials


class TestAuth:
    """Test cases for auth module."""

    def test_verify_credentials_success(self):
        """Test successful credential verification."""
        with patch.dict(os.environ, {"ADMIN_USERNAME": "testuser", "ADMIN_PASSWORD": "testpass"}):
            # Reload the module to get updated environment variables
            import importlib
            import app.api.v1.auth
            importlib.reload(app.api.v1.auth)
            
            credentials = HTTPBasicCredentials(username="testuser", password="testpass")
            result = app.api.v1.auth.verify_credentials(credentials)
            
            assert result == credentials

    def test_verify_credentials_wrong_username(self):
        """Test credential verification with wrong username."""
        with patch.dict(os.environ, {"ADMIN_USERNAME": "testuser", "ADMIN_PASSWORD": "testpass"}):
            import importlib
            import app.api.v1.auth
            importlib.reload(app.api.v1.auth)
            
            credentials = HTTPBasicCredentials(username="wronguser", password="testpass")
            
            with pytest.raises(HTTPException) as exc_info:
                app.api.v1.auth.verify_credentials(credentials)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert exc_info.value.detail == "Incorrect username or password"
            assert exc_info.value.headers == {"WWW-Authenticate": "Basic"}

    def test_verify_credentials_wrong_password(self):
        """Test credential verification with wrong password."""
        with patch.dict(os.environ, {"ADMIN_USERNAME": "testuser", "ADMIN_PASSWORD": "testpass"}):
            import importlib
            import app.api.v1.auth
            importlib.reload(app.api.v1.auth)
            
            credentials = HTTPBasicCredentials(username="testuser", password="wrongpass")
            
            with pytest.raises(HTTPException) as exc_info:
                app.api.v1.auth.verify_credentials(credentials)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert exc_info.value.detail == "Incorrect username or password"

    def test_verify_credentials_both_wrong(self):
        """Test credential verification with both username and password wrong."""
        with patch.dict(os.environ, {"ADMIN_USERNAME": "testuser", "ADMIN_PASSWORD": "testpass"}):
            import importlib
            import app.api.v1.auth
            importlib.reload(app.api.v1.auth)
            
            credentials = HTTPBasicCredentials(username="wronguser", password="wrongpass")
            
            with pytest.raises(HTTPException) as exc_info:
                app.api.v1.auth.verify_credentials(credentials)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_verify_credentials_default_credentials(self):
        """Test credential verification with default credentials."""
        # Clear environment variables to test defaults
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import app.api.v1.auth
            importlib.reload(app.api.v1.auth)
            
            credentials = HTTPBasicCredentials(username="admin", password="changeme")
            result = app.api.v1.auth.verify_credentials(credentials)
            
            assert result == credentials

    def test_verify_credentials_case_sensitivity(self):
        """Test that credentials are case sensitive."""
        with patch.dict(os.environ, {"ADMIN_USERNAME": "TestUser", "ADMIN_PASSWORD": "TestPass"}):
            import importlib
            import app.api.v1.auth
            importlib.reload(app.api.v1.auth)
            
            # Wrong case username
            credentials = HTTPBasicCredentials(username="testuser", password="TestPass")
            with pytest.raises(HTTPException):
                app.api.v1.auth.verify_credentials(credentials)
            
            # Wrong case password
            credentials = HTTPBasicCredentials(username="TestUser", password="testpass")
            with pytest.raises(HTTPException):
                app.api.v1.auth.verify_credentials(credentials)
            
            # Correct case
            credentials = HTTPBasicCredentials(username="TestUser", password="TestPass")
            result = app.api.v1.auth.verify_credentials(credentials)
            assert result == credentials

    def test_verify_credentials_empty_credentials(self):
        """Test credential verification with empty credentials."""
        with patch.dict(os.environ, {"ADMIN_USERNAME": "testuser", "ADMIN_PASSWORD": "testpass"}):
            import importlib
            import app.api.v1.auth
            importlib.reload(app.api.v1.auth)
            
            credentials = HTTPBasicCredentials(username="", password="")
            
            with pytest.raises(HTTPException) as exc_info:
                app.api.v1.auth.verify_credentials(credentials)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_verify_credentials_special_characters(self):
        """Test credential verification with special characters."""
        with patch.dict(os.environ, {"ADMIN_USERNAME": "user@domain.com", "ADMIN_PASSWORD": "pass!@#$%"}):
            import importlib
            import app.api.v1.auth
            importlib.reload(app.api.v1.auth)
            
            credentials = HTTPBasicCredentials(username="user@domain.com", password="pass!@#$%")
            result = app.api.v1.auth.verify_credentials(credentials)
            
            assert result == credentials

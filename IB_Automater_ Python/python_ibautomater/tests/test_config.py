"""
Tests for the configuration module
"""

import pytest
from pathlib import Path
import tempfile
import os

from ibautomater.config import IBConfig, TradingMode, Region
from ibautomater.exceptions import ConfigurationError


class TestIBConfig:
    """Test cases for IBConfig"""
    
    def setup_method(self):
        """Setup test environment"""
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Cleanup test environment"""
        # Clean up temporary directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_valid_config(self):
        """Test creating a valid configuration"""
        config = IBConfig(
            ib_directory=self.temp_dir,
            ib_version="10.19",
            username="testuser",
            password="testpass",
            trading_mode=TradingMode.PAPER,
            port=7497
        )
        
        assert config.ib_directory == self.temp_dir
        assert config.ib_version == "10.19"
        assert config.username == "testuser"
        assert config.password == "testpass"
        assert config.trading_mode == TradingMode.PAPER
        assert config.port == 7497
        assert config.export_logs == False
        assert config.region == Region.US
    
    def test_invalid_directory(self):
        """Test configuration with invalid directory"""
        with pytest.raises(ValueError, match="IB directory does not exist"):
            IBConfig(
                ib_directory="/nonexistent/path",
                ib_version="10.19",
                username="testuser",
                password="testpass",
                trading_mode=TradingMode.PAPER,
                port=7497
            )
    
    def test_invalid_port(self):
        """Test configuration with invalid port"""
        with pytest.raises(ValueError, match="Port must be between"):
            IBConfig(
                ib_directory=self.temp_dir,
                ib_version="10.19",
                username="testuser",
                password="testpass",
                trading_mode=TradingMode.PAPER,
                port=100  # Invalid port
            )
    
    def test_empty_credentials(self):
        """Test configuration with empty credentials"""
        with pytest.raises(ValueError, match="Username and password are required"):
            IBConfig(
                ib_directory=self.temp_dir,
                ib_version="10.19",
                username="",
                password="testpass",
                trading_mode=TradingMode.PAPER,
                port=7497
            )
    
    def test_trading_modes(self):
        """Test different trading modes"""
        # Test PAPER mode
        config_paper = IBConfig(
            ib_directory=self.temp_dir,
            ib_version="10.19",
            username="testuser",
            password="testpass",
            trading_mode=TradingMode.PAPER,
            port=7497
        )
        assert config_paper.trading_mode == TradingMode.PAPER
        
        # Test LIVE mode
        config_live = IBConfig(
            ib_directory=self.temp_dir,
            ib_version="10.19",
            username="testuser",
            password="testpass",
            trading_mode=TradingMode.LIVE,
            port=7496
        )
        assert config_live.trading_mode == TradingMode.LIVE
    
    def test_gateway_executable_paths(self):
        """Test gateway executable path generation"""
        config = IBConfig(
            ib_directory=self.temp_dir,
            ib_version="10.19",
            username="testuser",
            password="testpass",
            trading_mode=TradingMode.PAPER,
            port=7497
        )
        
        # Test that path is generated (actual path depends on platform)
        executable = config.gateway_executable
        assert isinstance(executable, str)
        assert self.temp_dir in executable
    
    def test_gateway_args(self):
        """Test gateway command line arguments generation"""
        config = IBConfig(
            ib_directory=self.temp_dir,
            ib_version="10.19",
            username="testuser",
            password="testpass",
            trading_mode=TradingMode.PAPER,
            port=7497,
            export_logs=True
        )
        
        args = config.get_gateway_args()
        assert isinstance(args, list)
        assert len(args) > 0
        
        # Check that important arguments are present
        args_str = " ".join(args)
        assert "-Dport=7497" in args_str
        assert "-Dmode=paper" in args_str
        assert "-Dexport.logs=true" in args_str


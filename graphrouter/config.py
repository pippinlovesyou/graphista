"""Configuration management for GraphRouter."""
import os
from typing import Optional, Dict, Any, cast
from pathlib import Path

class Config:
    """Configuration handler for GraphRouter."""

    @staticmethod
    def get_env(key: str, default: Optional[str] = None) -> Optional[str]:
        """Get environment variable from either Replit secrets or .env file.

        Args:
            key: Environment variable key
            default: Default value if key is not found

        Returns:
            str: Value of environment variable or default

        Note:
            Will check Replit secrets first, then fall back to .env file
        """
        # First try Replit secrets
        value = os.environ.get(key)
        if value is not None:
            return value

        # Then try .env file
        env_path = Path('.env')
        if env_path.exists():
            with env_path.open() as f:
                for line in f:
                    if '=' in line:
                        k, v = line.strip().split('=', 1)
                        if k == key:
                            return v.strip('"\'')

        return default

    @staticmethod
    def get_int_env(key: str, default: int) -> int:
        """Get integer environment variable with proper type casting.

        Args:
            key: Environment variable key
            default: Default value if key is not found or invalid

        Returns:
            int: Value of environment variable or default
        """
        value = Config.get_env(key)
        try:
            return int(value) if value is not None else default
        except (ValueError, TypeError):
            return default

    @staticmethod
    def get_falkordb_config() -> Dict[str, Any]:
        """Get FalkorDB configuration from environment.

        Returns:
            Dict containing FalkorDB connection configuration

        Note:
            Will set sensible defaults for non-critical parameters
        """
        return {
            'host': Config.get_env('FALKORDB_HOST', 'localhost'),
            'port': Config.get_int_env('FALKORDB_PORT', 6379),
            'username': Config.get_env('FALKORDB_USERNAME'),
            'password': Config.get_env('FALKORDB_PASSWORD'),
            'graph_name': Config.get_env('FALKORDB_GRAPH', 'graph')
        }
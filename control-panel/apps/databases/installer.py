"""
Database dependency installer following the pattern from setup.sh.

This module provides consistent installer methods across all database types,
with proper dependency checking, status reporting, and error handling.
"""

import sys
import subprocess
import importlib
from typing import Dict, List, Tuple, Optional
from .adapters.base import DatabaseType


class DatabaseInstaller:
    """
    Handles installation of database dependencies and services.
    
    Follows the same pattern as the database installation process in setup.sh,
    with proper dependency checking, status reporting, and error handling.
    """
    
    # Define dependencies for each database type
    DEPENDENCIES = {
        DatabaseType.POSTGRESQL: ['psycopg2-binary'],
        DatabaseType.MYSQL: ['pymysql'],
        DatabaseType.MONGODB: ['pymongo'],
        DatabaseType.REDIS: ['redis'],
        DatabaseType.PINECONE: ['pinecone-client'],
        DatabaseType.SQLITE: [],  # No external dependencies needed
    }
    
    # Define import names for checking if dependencies are installed
    IMPORT_NAMES = {
        'psycopg2-binary': 'psycopg2',
        'pymysql': 'pymysql',
        'pymongo': 'pymongo',
        'redis': 'redis',
        'pinecone-client': 'pinecone',
    }
    
    @classmethod
    def check_dependencies(cls, db_type: DatabaseType) -> Tuple[bool, List[str]]:
        """
        Check if all dependencies for a database type are installed.
        
        Args:
            db_type: The database type to check
            
        Returns:
            Tuple of (all_installed, missing_dependencies)
        """
        if db_type not in cls.DEPENDENCIES:
            return True, []
            
        dependencies = cls.DEPENDENCIES[db_type]
        missing = []
        
        for dep in dependencies:
            import_name = cls.IMPORT_NAMES.get(dep, dep)
            try:
                # Try to import the module
                module = importlib.import_module(import_name)
                # Additional check: try to access a common attribute to ensure it's properly loaded
                if hasattr(module, '__version__'):
                    pass  # Module is properly loaded
                elif import_name == 'psycopg2':
                    # psycopg2 might not have __version__ in all versions
                    hasattr(module, 'connect')
                elif import_name == 'pymysql':
                    # Check if pymysql has connect method
                    hasattr(module, 'connect')
                elif import_name == 'redis':
                    # Check if redis has Redis class
                    hasattr(module, 'Redis')
                elif import_name == 'pymongo':
                    # Check if pymongo has MongoClient
                    hasattr(module, 'MongoClient')
                elif import_name == 'pinecone':
                    # Check if pinecone has init method
                    hasattr(module, 'init')
            except ImportError as e:
                missing.append(dep)
                # Log the specific import error for debugging
                print(f"Failed to import {import_name} for dependency {dep}: {e}")
            except Exception as e:
                missing.append(dep)
                # Log any other errors during import checking
                print(f"Error checking dependency {dep} ({import_name}): {e}")
                
        return len(missing) == 0, missing
    
    @classmethod
    def install_dependency(cls, dependency: str) -> Tuple[bool, str, str]:
        """
        Install a single dependency using pip.
        
        Args:
            dependency: The dependency to install
            
        Returns:
            Tuple of (success, output, error)
        """
        try:
            install_cmd = [sys.executable, '-m', 'pip', 'install', dependency]
            result = subprocess.run(
                install_cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Installation timed out"
        except Exception as e:
            return False, "", str(e)
    
    @classmethod
    def install_dependencies(cls, db_type: DatabaseType) -> Dict[str, Dict[str, str]]:
        """
        Install all dependencies for a database type.
        
        Args:
            db_type: The database type to install dependencies for
            
        Returns:
            Dictionary with installation results for each dependency
        """
        if db_type not in cls.DEPENDENCIES:
            return {}
            
        dependencies = cls.DEPENDENCIES[db_type]
        results = {}
        
        for dep in dependencies:
            success, output, error = cls.install_dependency(dep)
            results[dep] = {
                'success': success,
                'output': output,
                'error': error
            }
            
        return results
    
    @classmethod
    def get_install_command(cls, dependency: str) -> str:
        """
        Get the pip install command for a dependency.
        
        Args:
            dependency: The dependency to get the command for
            
        Returns:
            The pip install command
        """
        return f"pip install {dependency}"
    
    @classmethod
    def get_dependency_info(cls, db_type: DatabaseType) -> Dict:
        """
        Get information about dependencies for a database type.
        
        Args:
            db_type: The database type to get info for
            
        Returns:
            Dictionary with dependency information
        """
        if db_type not in cls.DEPENDENCIES:
            return {
                'dependencies': [],
                'all_installed': True,
                'missing': [],
                'install_commands': {}
            }
            
        dependencies = cls.DEPENDENCIES[db_type]
        all_installed, missing = cls.check_dependencies(db_type)
        
        return {
            'dependencies': dependencies,
            'all_installed': all_installed,
            'missing': missing,
            'install_commands': {
                dep: cls.get_install_command(dep) for dep in dependencies
            }
        }


class DatabaseServiceInstaller:
    """
    Handles installation of database services (PostgreSQL, MySQL, Redis, etc.).
    
    Follows the same pattern as the service installation in setup.sh,
    with proper status checking, error handling, and validation.
    """
    
    @classmethod
    def check_service_status(cls, service_name: str) -> Tuple[bool, str]:
        """
        Check if a system service is running.
        
        Args:
            service_name: The name of the service to check
            
        Returns:
            Tuple of (is_running, status_output)
        """
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', service_name],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            is_running = result.returncode == 0 and result.stdout.strip() == 'active'
            return is_running, result.stdout.strip()
        except subprocess.TimeoutExpired:
            return False, "Status check timed out"
        except Exception as e:
            return False, str(e)
    
    @classmethod
    def start_service(cls, service_name: str) -> Tuple[bool, str]:
        """
        Start a system service.
        
        Args:
            service_name: The name of the service to start
            
        Returns:
            Tuple of (success, output)
        """
        try:
            result = subprocess.run(
                ['systemctl', 'start', service_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return result.returncode == 0, result.stdout.strip()
        except subprocess.TimeoutExpired:
            return False, "Service start timed out"
        except Exception as e:
            return False, str(e)
    
    @classmethod
    def enable_service(cls, service_name: str) -> Tuple[bool, str]:
        """
        Enable a system service to start on boot.
        
        Args:
            service_name: The name of the service to enable
            
        Returns:
            Tuple of (success, output)
        """
        try:
            result = subprocess.run(
                ['systemctl', 'enable', service_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return result.returncode == 0, result.stdout.strip()
        except subprocess.TimeoutExpired:
            return False, "Service enable timed out"
        except Exception as e:
            return False, str(e)
    
    @classmethod
    def install_service_package(cls, package_name: str) -> Tuple[bool, str]:
        """
        Install a system package for a database service.
        
        Args:
            package_name: The name of the package to install
            
        Returns:
            Tuple of (success, output)
        """
        try:
            result = subprocess.run(
                ['apt-get', 'install', '-y', package_name],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            return result.returncode == 0, result.stdout.strip()
        except subprocess.TimeoutExpired:
            return False, "Package installation timed out"
        except Exception as e:
            return False, str(e)
    
    @classmethod
    def update_package_list(cls) -> Tuple[bool, str]:
        """
        Update the system package list.
        
        Returns:
            Tuple of (success, output)
        """
        try:
            result = subprocess.run(
                ['apt-get', 'update', '-y'],
                capture_output=True,
                text=True,
                timeout=120  # 2 minutes timeout
            )
            
            return result.returncode == 0, result.stdout.strip()
        except subprocess.TimeoutExpired:
            return False, "Package list update timed out"
        except Exception as e:
            return False, str(e)
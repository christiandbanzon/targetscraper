#!/usr/bin/env python3
"""
Setup script for Target Scraper
"""

import os
import subprocess
import sys

def create_env_file():
    """Create .env file from template if it doesn't exist"""
    if not os.path.exists('.env'):
        if os.path.exists('env.example'):
            print("Creating .env file from template...")
            with open('env.example', 'r') as template:
                content = template.read()
            
            with open('.env', 'w') as env_file:
                env_file.write(content)
            print("SUCCESS: .env file created! Please edit it with your credentials.")
        else:
            print("ERROR: env.example not found!")
            return False
    else:
        print("SUCCESS: .env file already exists!")
    return True

def install_dependencies():
    """Install required Python packages"""
    print("Installing Python dependencies...")
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
        print("SUCCESS: Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to install dependencies: {e}")
        return False

def create_directories():
    """Create necessary directories"""
    directories = ['outputs', 'logs']
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"SUCCESS: Created directory: {directory}")

def main():
    """Main setup function"""
    print("Setting up Target Scraper...")
    print("=" * 50)
    
    # Create directories
    create_directories()
    
    # Create .env file
    if not create_env_file():
        return False
    
    # Install dependencies
    if not install_dependencies():
        return False
    
    print("\n" + "=" * 50)
    print("SUCCESS: Setup complete!")
    print("\nNext steps:")
    print("1. Edit .env file with your Oxylabs credentials")
    print("2. Start API: uvicorn main:app --host 0.0.0.0 --port 8000")
    print("3. Or use Docker: docker-compose up -d")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

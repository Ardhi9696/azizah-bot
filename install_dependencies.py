#!/usr/bin/env python3
import subprocess
import sys

def install_packages():
    packages = [
        "anyio==4.11.0",
        "APScheduler==3.10.4", 
        "beautifulsoup4==4.14.2",
        "certifi==2025.11.12",
        "charset-normalizer==3.4.4",
        "colorlog==6.10.1",
        "h11==0.16.0",
        "httpcore==1.0.9",
        "httpx==0.25.2",
        "idna==3.11",
        "printdirtree==0.1.5",
        "pyperclip==1.11.0",
        "python-dateutil==2.9.0.post0",
        "python-dotenv==1.2.1",
        "python-telegram-bot==20.7",
        "pytz==2025.2",
        "requests==2.32.5",
        "six==1.17.0",
        "sniffio==1.3.1",
        "soupsieve==2.8",
        "typing_extensions==4.15.0",
        "tzlocal==5.3.1",
        "urllib3==2.5.0"
    ]
    
    print("🚀 Installing dependencies...")
    
    for package in packages:
        try:
            print(f"📦 Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"✅ {package} installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install {package}: {e}")
    
    print("🎉 All dependencies installed!")

if __name__ == "__main__":
    install_packages()

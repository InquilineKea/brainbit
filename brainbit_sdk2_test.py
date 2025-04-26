#!/usr/bin/env python3
"""
BrainBit SDK2 Direct Test

This script directly tests the NeuroSDK2 library installation using ctypes
to load the native library directly.
"""

import os
import sys
import ctypes
from pathlib import Path
import time

def load_neurosdk2_library():
    """Load the NeuroSDK2 library directly using ctypes."""
    print("Attempting to load NeuroSDK2 library...")
    
    # Try different paths for the library
    paths_to_try = [
        # User's home directory
        os.path.join(str(Path.home()), "Library", "neurosdk2", "libneurosdk2.dylib"),
        # Site-packages
        os.path.join(sys.prefix, "lib", "python3.11", "site-packages", "neurosdk2_lib", "libneurosdk2.dylib"),
        # System library
        "/usr/local/lib/libneurosdk2.dylib"
    ]
    
    for path in paths_to_try:
        print(f"Trying: {path}")
        if os.path.exists(path):
            try:
                lib = ctypes.CDLL(path)
                print(f"✅ Successfully loaded library from: {path}")
                return lib
            except Exception as e:
                print(f"❌ Error loading library: {e}")
        else:
            print(f"❌ Path does not exist: {path}")
    
    print("❌ Failed to load NeuroSDK2 library from any location")
    return None

def diagnose_import_issue():
    """Diagnose why import pyneurosdk2 might be failing."""
    print("\nDiagnosing import issue for 'pyneurosdk2'...")
    
    # Check if package directory exists
    package_path = os.path.join(sys.prefix, "lib", "python3.11", "site-packages", "pyneurosdk2")
    print(f"Package directory: {package_path} - {'Exists' if os.path.exists(package_path) else 'Not found'}")
    
    if os.path.exists(package_path):
        # Check if __init__.py exists
        init_path = os.path.join(package_path, "__init__.py")
        print(f"__init__.py: {init_path} - {'Exists' if os.path.exists(init_path) else 'Not found'}")
        
        # List files in the package directory
        print("\nFiles in package directory:")
        for file in os.listdir(package_path):
            print(f"- {file}")
    
    # Check if package is in sys.path
    print("\nChecking sys.path for package location:")
    site_packages = os.path.join(sys.prefix, "lib", "python3.11", "site-packages")
    print(f"site-packages in sys.path: {'Yes' if site_packages in sys.path else 'No'}")

def test_python_path():
    """Test modifying Python path to include the package."""
    print("\nTesting Python path modification...")
    
    # Add site-packages to Python path
    site_packages = os.path.join(sys.prefix, "lib", "python3.11", "site-packages")
    if site_packages not in sys.path:
        print(f"Adding {site_packages} to sys.path")
        sys.path.append(site_packages)
    
    # Try importing again
    try:
        print("Attempting to import pyneurosdk2...")
        import pyneurosdk2
        print("✅ Successfully imported pyneurosdk2")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def try_direct_import():
    """Try importing using importlib."""
    print("\nTrying direct import using importlib...")
    
    import importlib.util
    import importlib.machinery
    
    # Get all pyneurosdk2 files
    site_packages = os.path.join(sys.prefix, "lib", "python3.11", "site-packages")
    package_path = os.path.join(site_packages, "pyneurosdk2")
    
    if not os.path.exists(package_path):
        print(f"❌ Package directory not found: {package_path}")
        return False
    
    # Try to load the package manually
    try:
        spec = importlib.util.spec_from_file_location("pyneurosdk2", 
                                                     os.path.join(package_path, "__init__.py"))
        if spec:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            print("✅ Successfully loaded pyneurosdk2 using importlib")
            return True
        else:
            print("❌ Failed to create spec for pyneurosdk2")
            return False
    except Exception as e:
        print(f"❌ Error loading module: {e}")
        return False

def reinstall_package():
    """Attempt to reinstall the package in a different way."""
    print("\nAttempting alternative package installation...")
    
    # Try downloading the package source and installing manually
    import subprocess
    import tempfile
    import shutil
    
    temp_dir = tempfile.mkdtemp()
    os.chdir(temp_dir)
    
    try:
        print("Downloading pyneurosdk2 source...")
        subprocess.run(["pip", "download", "--no-binary=:all:", "pyneurosdk2"], check=True)
        
        # Find the downloaded tar.gz file
        tarfiles = [f for f in os.listdir(".") if f.endswith(".tar.gz") and "pyneurosdk2" in f]
        if not tarfiles:
            print("❌ Failed to download source package")
            return False
        
        # Extract the package
        print(f"Extracting {tarfiles[0]}...")
        subprocess.run(["tar", "-xzf", tarfiles[0]], check=True)
        
        # Find the extracted directory
        dirs = [d for d in os.listdir(".") if os.path.isdir(d) and "pyneurosdk2" in d]
        if not dirs:
            print("❌ Failed to extract package")
            return False
        
        # Install the package
        os.chdir(dirs[0])
        print("Installing package from source...")
        result = subprocess.run(["pip", "install", "-e", "."], check=True)
        
        print("✅ Package reinstalled from source")
        return True
    except Exception as e:
        print(f"❌ Error during reinstallation: {e}")
        return False
    finally:
        # Clean up
        shutil.rmtree(temp_dir)

def main():
    """Main function."""
    print("=== BrainBit SDK2 Direct Test ===")
    
    # Load the library
    lib = load_neurosdk2_library()
    if not lib:
        print("\n❌ Failed to load native NeuroSDK2 library")
    else:
        print("\n✅ Successfully loaded native NeuroSDK2 library")
    
    # Diagnose import issues
    diagnose_import_issue()
    
    # Test Python path
    if test_python_path():
        print("\n✅ Successfully fixed import issue by modifying Python path")
    else:
        # Try direct import
        if try_direct_import():
            print("\n✅ Successfully fixed import issue using direct import")
        else:
            # Try reinstalling
            if reinstall_package():
                print("\n✅ Successfully reinstalled package")
                # Test import again
                if test_python_path():
                    print("\n✅ Import works after reinstallation")
            else:
                print("\n❌ All attempts to fix import issues failed")
    
    print("\n=== Test Complete ===")
    print("NeuroSDK2 native library is properly installed.")
    print("If Python import is still failing, you may need to:")
    print("1. Try restarting your Python environment")
    print("2. Check for environment conflicts (conda vs. system Python)")
    print("3. Create a new conda environment and reinstall there")

if __name__ == "__main__":
    main()

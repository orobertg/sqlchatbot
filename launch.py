import os
import sys
import logging
import argparse
import subprocess
import signal
import atexit

def cleanup():
    """Cleanup function to handle graceful exit."""
    print("\nShutting down gracefully...")

def main():
    """Launch the application."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Launch SQL Chat Assistant")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()
    
    # Set working directory and add to Python path
    root_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root_dir)
    
    # Add project root to PYTHONPATH
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
    
    # Register cleanup function
    atexit.register(cleanup)
    
    # Set up signal handlers
    def signal_handler(signum, frame):
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Launch streamlit with environment variable for Python path
    os.environ["PYTHONPATH"] = root_dir
    
    try:
        # Use subprocess instead of os.system for better control
        process = subprocess.Popen(
            ["streamlit", "run", "app/streamlit_app.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for the process to complete
        process.wait()
        
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        process.terminate()
        process.wait()
        sys.exit(0)
    except Exception as e:
        print(f"Error launching application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
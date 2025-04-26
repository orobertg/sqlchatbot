import os
import subprocess
import sys

# Ensure that the current working directory is at the beginning of PYTHONPATH.
sys.path.insert(0, os.path.abspath(os.getcwd()))

print("Current working directory:", os.getcwd())
print("Python sys.path:")
for path in sys.path:
    print("  ", path)

if os.path.exists(".env"):
    try:
        # Set the PYTHONPATH for the subprocess so that 'backend' is found.
        env = os.environ.copy()
        env["PYTHONPATH"] = os.path.abspath(os.getcwd())
        subprocess.run(
            ["streamlit", "run", "app/streamlit_app.py"],
            env=env,
            check=True
        )
    except KeyboardInterrupt:
        print("\n🔴 Streamlit app interrupted by user (CTRL+C). Exiting cleanly...")
    except Exception as e:
        print(f"An error occurred while running the app: {e}")
else:
    print("❌ Please create a .env file before launching.")
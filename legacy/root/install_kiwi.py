import subprocess
import os

def install():
    try:
        # Use relative path since we'll run from the project root
        python_exe = os.path.join(".venv", "Scripts", "python.exe")
        result = subprocess.run(
            [python_exe, "-m", "pip", "install", "kiwipiepy==0.22.2"],
            capture_output=True,
            text=True
        )
        with open("install_log_py.txt", "w", encoding="utf-8") as f:
            f.write(f"STDOUT:\n{result.stdout}\n")
            f.write(f"STDERR:\n{result.stderr}\n")
            f.write(f"EXIT CODE: {result.returncode}\n")
        print(f"Finished with exit code {result.returncode}")
    except Exception as e:
        with open("install_log_py.txt", "w", encoding="utf-8") as f:
            f.write(f"ERROR: {str(e)}\n")
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    install()

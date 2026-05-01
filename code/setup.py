"""
setup.py — One-command setup for the Forensic Triage Agent

This script handles:
1. Virtual environment creation (if needed)
2. Dependency installation
3. Environment validation
4. Ready-to-run verification

Usage:
    python setup.py
"""

import os
import sys
import subprocess
from pathlib import Path

def run_command(cmd, description):
    """Run a shell command and report status."""
    print(f"\n[*] {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[!] Error: {result.stderr}")
            return False
        print(f"[+] {description} - OK")
        return True
    except Exception as e:
        print(f"[!] Error running command: {e}")
        return False

def main():
    print("""
    ====================================================================
    Forensic Triage Agent -- Setup & Configuration
    HackerRank Orchestrate May 2026
    ====================================================================
    """)

    # Step 1: Check Python version
    print(f"[+] Python version: {sys.version.split()[0]}")
    if sys.version_info < (3, 8):
        print("[!] Python 3.8+ required")
        sys.exit(1)

    # Step 2: Create virtual environment if needed
    venv_path = Path("venv")
    if not venv_path.exists():
        if not run_command(f"{sys.executable} -m venv venv", "Creating virtual environment"):
            sys.exit(1)
    else:
        print("\n[+] Virtual environment already exists")

    # Step 3: Determine pip path
    if sys.platform == "win32":
        pip_cmd = "venv\\Scripts\\pip"
        activate_cmd = "venv\\Scripts\\activate.bat"
    else:
        pip_cmd = "venv/bin/pip"
        activate_cmd = "source venv/bin/activate"

    # Step 4: Install dependencies
    deps = [
        "groq>=0.4.0",
        "rank-bm25>=0.2.2",
        "rich>=13.7.0",
        "python-dotenv>=1.0.0",
        "langdetect>=1.0.9",
        "tiktoken>=0.6.0"
    ]

    print(f"\n[*] Installing dependencies...")
    for dep in deps:
        result = subprocess.run(
            f"{pip_cmd} install -q {dep}",
            shell=True,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"[!] Failed to install {dep}")
            print(result.stderr)
            sys.exit(1)
        print(f"    [+] {dep}")

    # Step 5: Validate paths
    print("\n[*] Validating directory structure...")
    required_dirs = [
        ("../data", "Documentation corpus"),
        ("../support_tickets", "Support tickets"),
    ]

    for dir_path, description in required_dirs:
        if Path(dir_path).exists():
            print(f"    [+] {description}: {dir_path}")
        else:
            print(f"    [!] Missing: {dir_path}")
            print(f"       Run this script from the code/ directory")
            sys.exit(1)

    # Step 6: Validate .env
    print("\n[*] Checking configuration...")
    env_path = Path("../.env")
    if env_path.exists():
        with open(env_path) as f:
            content = f.read()
            if "GROQ_API_KEY" in content:
                # Check if it's a placeholder
                if "gsk-" in content and "gsk-your-key" not in content:
                    print(f"    [+] GROQ_API_KEY configured")
                else:
                    print(f"    [!] GROQ_API_KEY is a placeholder")
                    print(f"       Edit ../.env and add your actual API key")
            else:
                print(f"    [!] GROQ_API_KEY not found in .env")
                print(f"       Edit ../.env and add: GROQ_API_KEY=gsk-your-key")
    else:
        print(f"    [!] .env file not found at ../.env")
        print(f"       Copy .env.example to .env and configure API key")

    # Step 7: Verify Python modules
    print("\n[*] Verifying Python modules...")
    modules = ["groq", "rank_bm25", "rich", "dotenv", "langdetect"]
    try:
        for module in modules:
            __import__(module)
            print(f"    [+] {module}")
    except ImportError as e:
        print(f"    [!] Missing module: {e}")
        sys.exit(1)

    # Step 8: Test imports
    print("\n[*] Testing code imports...")
    try:
        import config
        import safety
        import router
        import retriever
        import generator
        import auditor
        import agent
        import formatter
        print("    [+] All modules import successfully")
    except Exception as e:
        print(f"    [!] Import error: {e}")
        sys.exit(1)

    # Final summary
    print(f"""
    ====================================================================
    SETUP COMPLETE - OK
    ====================================================================

    Quick Start:
    -------------------------------------------------------------------

    1. Configure API key:
       Edit ../.env and add: GROQ_API_KEY=gsk-your-actual-key

    2. Validate setup (no API calls):
       Windows: run.bat --dry-run
       Unix:    ./run.sh --dry-run

    3. Test on sample tickets:
       Windows: run.bat --sample
       Unix:    ./run.sh --sample

    4. Process full dataset:
       Windows: run.bat
       Unix:    ./run.sh

    5. View results:
       cat ../support_tickets/output.csv

    -------------------------------------------------------------------
    Ready to run! Just set your GROQ_API_KEY and execute run.bat/run.sh
    ====================================================================
    """)

if __name__ == "__main__":
    main()

"""Clean up the agent/ folder for AgentCore Runtime deployment.

Removes duplicate dependency directories, unnecessary packages,
and installs the missing bedrock-agentcore package.

Run from the project root:
    python cleanup_agent.py
"""

import os
import shutil
import subprocess
import sys

AGENT_DIR = os.path.join(os.path.dirname(__file__), "agent")

# ---------------------------------------------------------------------------
# 1. Source code to KEEP (your actual agent code)
# ---------------------------------------------------------------------------
SOURCE_KEEP = {
    "main.py",
    "system_prompt.txt",
    "pyproject.toml",
    "model",       # model/load.py
    "tools",       # tools/*.py
    "shared",      # shared/sf_client.py
}

# ---------------------------------------------------------------------------
# 2. Required dependency packages (what your agent actually imports)
# ---------------------------------------------------------------------------
# Traced from main.py → model/ → tools/ → shared/ imports:
#   bedrock_agentcore  (BedrockAgentCoreApp — MISSING, must install)
#   strands            (Agent, tool, BedrockModel)
#   boto3 → botocore, jmespath, s3transfer, dateutil, urllib3
#   pydantic → pydantic_core, annotated_types
#   typing_extensions
#   docstring_parser   (strands dep)
#   opentelemetry*     (strands dep)
#   wrapt              (strands dep)
#   tenacity           (strands dep)
#   httpx → httpcore, h11, idna, certifi, anyio, sniffio
#   pydantic_settings → dotenv
#   starlette          (bedrock_agentcore runtime dep)
#   uvicorn            (bedrock_agentcore runtime dep)
#   sse_starlette      (bedrock_agentcore runtime dep)
#   click              (bedrock_agentcore CLI dep)
#   packaging          (various dep)
#   typing_inspection  (pydantic dep)
#   importlib_metadata (fallback for older Python)
#   zipp               (importlib_metadata dep)
#   requests → charset_normalizer (boto/botocore dep)
#   cffi, cryptography (auth/signing deps)
#   pycparser          (cffi dep)
#   aws_requests_auth  (AWS auth)
#   multipart / python_multipart (starlette dep)
#   httpx_sse          (bedrock_agentcore dep)

REQUIRED_PACKAGES = {
    # --- Core agent framework ---
    "strands",
    "strands_agents-1.34.1.dist-info",
    # --- AgentCore Runtime (must install — currently missing!) ---
    "bedrock_agentcore",
    # --- boto3 chain ---
    "boto3",
    "boto3-1.42.81.dist-info",
    "botocore",
    "botocore-1.42.81.dist-info",
    "jmespath",
    "jmespath-1.1.0.dist-info",
    "s3transfer",
    "s3transfer-0.16.0.dist-info",
    "dateutil",
    "python_dateutil-2.9.0.post0.dist-info",
    "urllib3",
    "urllib3-2.6.3.dist-info",
    # --- pydantic chain ---
    "pydantic",
    "pydantic-2.12.5.dist-info",
    "pydantic_core",
    "pydantic_core-2.41.5.dist-info",
    "annotated_types",
    "annotated_types-0.7.0.dist-info",
    "pydantic_settings",
    "pydantic_settings-2.13.1.dist-info",
    "typing_extensions.py",
    "typing_extensions-4.15.0.dist-info",
    "typing_inspection",
    "typing_inspection-0.4.2.dist-info",
    # --- strands deps ---
    "docstring_parser",
    "docstring_parser-0.17.0.dist-info",
    "opentelemetry",
    "opentelemetry_api-1.40.0.dist-info",
    "opentelemetry_sdk-1.40.0.dist-info",
    "opentelemetry_semantic_conventions-0.61b0.dist-info",
    "opentelemetry_instrumentation-0.61b0.dist-info",
    "opentelemetry_instrumentation_threading-0.61b0.dist-info",
    "wrapt",
    "wrapt-1.17.3.dist-info",
    "tenacity",
    "tenacity-9.1.4.dist-info",
    # --- httpx chain ---
    "httpx",
    "httpx-0.28.1.dist-info",
    "httpx_sse",
    "httpx_sse-0.4.3.dist-info",
    "httpcore",
    "httpcore-1.0.9.dist-info",
    "h11",
    "h11-0.16.0.dist-info",
    "idna",
    "idna-3.11.dist-info",
    "certifi",
    "certifi-2026.2.25.dist-info",
    "anyio",
    "anyio-4.13.0.dist-info",
    # --- web server (bedrock_agentcore runtime) ---
    "starlette",
    "starlette-1.0.0.dist-info",
    "uvicorn",
    "uvicorn-0.42.0.dist-info",
    "sse_starlette",
    "sse_starlette-3.3.4.dist-info",
    "click",
    "click-8.3.1.dist-info",
    # --- dotenv (pydantic_settings) ---
    "dotenv",
    "python_dotenv-1.2.2.dist-info",
    # --- other required deps ---
    "packaging",
    "packaging-26.0.dist-info",
    "importlib_metadata",
    "importlib_metadata-8.7.1.dist-info",
    "zipp",
    "zipp-3.23.0.dist-info",
    "requests",
    "requests-2.33.1.dist-info",
    "charset_normalizer",
    "charset_normalizer-3.4.7.dist-info",
    "cffi",
    "cffi-2.0.0.dist-info",
    "cryptography",
    "cryptography-46.0.6.dist-info",
    "pycparser",
    "pycparser-3.0.dist-info",
    "aws_requests_auth",
    "aws_requests_auth-0.4.3.dist-info",
    "multipart",
    "python_multipart",
    "python_multipart-0.0.22.dist-info",
    # --- async deps ---
    "aiohttp",
    "aiohttp-3.13.5.dist-info",
    "aiosignal",
    "aiosignal-1.4.0.dist-info",
    "aiohappyeyeballs",
    "aiohappyeyeballs-2.6.1.dist-info",
    "frozenlist",
    "frozenlist-1.8.0.dist-info",
    "multidict",
    "multidict-6.7.1.dist-info",
    "propcache",
    "propcache-0.4.1.dist-info",
    "yarl",
    "yarl-1.23.0.dist-info",
    "attr",
    "attrs",
    "attrs-26.1.0.dist-info",
    # --- yaml (pydantic_settings / botocore) ---
    "yaml",
    "_yaml",
    "pyyaml-6.0.3.dist-info",
    # --- jsonschema (may be needed by strands) ---
    "jsonschema",
    "jsonschema-4.26.0.dist-info",
    "jsonschema_specifications",
    "jsonschema_specifications-2025.9.1.dist-info",
    "referencing",
    "referencing-0.37.0.dist-info",
    "rpds",
    "rpds_py-0.30.0.dist-info",
    # --- jwt (AWS auth) ---
    "jwt",
    "pyjwt-2.12.1.dist-info",
    # --- native .so files ---
    "_cffi_backend.cpython-313-x86_64-linux-gnu.so",
    "81d243bd2c585b0f4821__mypyc.cpython-313-x86_64-linux-gnu.so",
    # --- strands_tools (required by strands-agents) ---
    "strands_tools",
    "strands_agents_tools-0.3.0.dist-info",
}

# ---------------------------------------------------------------------------
# 3. Things to REMOVE (unnecessary for this agent)
# ---------------------------------------------------------------------------
REMOVE_DIRS = {
    # Duplicate dependency directories
    "vendor",
    "dependencies",
    # Unnecessary packages
    "sympy",
    "sympy-1.14.0.dist-info",
    "mpmath",
    "mpmath-1.3.0.dist-info",
    "PIL",
    "pillow-12.2.0.dist-info",
    "pillow.libs",
    "slack",
    "slack_bolt",
    "slack_bolt-1.27.0.dist-info",
    "slack_sdk",
    "slack_sdk-3.41.0.dist-info",
    "mcp",
    "mcp-1.27.0.dist-info",
    "markdownify",
    "markdownify-1.2.2.dist-info",
    "markdown_it",
    "markdown_it_py-4.0.0.dist-info",
    "mdurl",
    "mdurl-0.1.2.dist-info",
    "bs4",
    "beautifulsoup4-4.14.3.dist-info",
    "soupsieve",
    "soupsieve-2.8.3.dist-info",
    "prompt_toolkit",
    "prompt_toolkit-3.0.52.dist-info",
    "pygments",
    "pygments-2.20.0.dist-info",
    "rich",
    "rich-14.3.3.dist-info",
    "watchdog",
    "watchdog-6.0.0.dist-info",
    "dill",
    "dill-0.4.1.dist-info",
    "wcwidth",
    "wcwidth-0.6.0.dist-info",
    "six-1.17.0.dist-info",
    "bin",
    "share",
}

REMOVE_FILES = {
    "isympy.py",
    "six.py",
}


def dry_run():
    """Show what would be removed without actually removing anything."""
    print("=" * 60)
    print("DRY RUN — nothing will be deleted")
    print("=" * 60)

    entries = os.listdir(AGENT_DIR)
    to_remove = []
    to_keep = []

    for entry in sorted(entries):
        full = os.path.join(AGENT_DIR, entry)
        if entry in SOURCE_KEEP:
            to_keep.append(f"  [SOURCE] {entry}")
        elif entry in REQUIRED_PACKAGES:
            to_keep.append(f"  [DEP]    {entry}")
        elif entry in REMOVE_DIRS or entry in REMOVE_FILES:
            size = _get_size(full)
            to_remove.append(f"  [REMOVE] {entry}  ({_fmt_size(size)})")
        elif entry == "__pycache__":
            to_remove.append(f"  [REMOVE] {entry}")
        else:
            to_keep.append(f"  [KEEP?]  {entry}")

    print("\nWill KEEP:")
    for line in to_keep:
        print(line)

    print(f"\nWill REMOVE ({len(to_remove)} items):")
    for line in to_remove:
        print(line)

    total_remove = sum(
        _get_size(os.path.join(AGENT_DIR, e))
        for e in entries
        if e in REMOVE_DIRS or e in REMOVE_FILES or e == "__pycache__"
    )
    print(f"\nTotal space freed: ~{_fmt_size(total_remove)}")
    print(f"\nMISSING CRITICAL: bedrock-agentcore (must be installed)")


def clean():
    """Actually remove unnecessary files and dirs."""
    print("Cleaning agent/ folder...")

    removed = 0
    for name in REMOVE_DIRS:
        path = os.path.join(AGENT_DIR, name)
        if os.path.isdir(path):
            print(f"  Removing directory: {name}")
            shutil.rmtree(path)
            removed += 1

    for name in REMOVE_FILES:
        path = os.path.join(AGENT_DIR, name)
        if os.path.isfile(path):
            print(f"  Removing file: {name}")
            os.remove(path)
            removed += 1

    # Remove __pycache__ dirs recursively
    for root, dirs, _files in os.walk(AGENT_DIR):
        for d in dirs:
            if d == "__pycache__":
                cache_path = os.path.join(root, d)
                print(f"  Removing: {os.path.relpath(cache_path, AGENT_DIR)}")
                shutil.rmtree(cache_path)
                removed += 1

    print(f"\nRemoved {removed} items.")


def install_bedrock_agentcore():
    """Install bedrock-agentcore into the agent/ folder for Linux x86_64."""
    print("\nInstalling bedrock-agentcore into agent/ ...")
    cmd = [
        sys.executable, "-m", "pip", "install",
        "bedrock-agentcore",
        "--target", AGENT_DIR,
        "--platform", "manylinux2014_x86_64",
        "--python-version", "3.13",
        "--only-binary=:all:",
        "--no-deps",  # We already have the other deps
        "--upgrade",
    ]
    print(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR: pip install failed:\n{result.stderr}")
        print("\n  Trying without platform constraint (pure-python package)...")
        cmd_fallback = [
            sys.executable, "-m", "pip", "install",
            "bedrock-agentcore",
            "--target", AGENT_DIR,
            "--no-deps",
            "--upgrade",
        ]
        result = subprocess.run(cmd_fallback, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ERROR: fallback pip install also failed:\n{result.stderr}")
            return False
    print(f"  {result.stdout.strip()}")
    print("  bedrock-agentcore installed successfully.")
    return True


def _get_size(path):
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            total += os.path.getsize(os.path.join(root, f))
    return total


def _fmt_size(size_bytes):
    if size_bytes >= 1_073_741_824:
        return f"{size_bytes / 1_073_741_824:.1f} GB"
    if size_bytes >= 1_048_576:
        return f"{size_bytes / 1_048_576:.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--apply":
        clean()
        install_bedrock_agentcore()
        print("\nDone! Agent folder is cleaned and ready to zip.")
    else:
        dry_run()
        print("\nTo apply changes, run: python cleanup_agent.py --apply")

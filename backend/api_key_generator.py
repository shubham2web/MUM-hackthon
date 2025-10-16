import secrets
import os
import re
from datetime import datetime
from colorama import Fore, Style, init as colorama_init

# --- Configuration ---
# This script will find these files in the same directory it is run from.
ENV_FILE_PATH = ".env"
CLIENT_FILE_PATH = "professional_client.py"
# -----------------------------------------------------------

def generate_api_key(length=24):
    """Generates a secure, random hexadecimal string to be used as an API key."""
    return secrets.token_hex(length)

def update_file_key(filepath, new_key, prefix):
    """
    Reads a file, replaces the line starting with the given prefix,
    and writes the file back. This version is case-insensitive and uses UTF-8.
    """
    if not os.path.exists(filepath):
        print(f"{Fore.RED}❌ Error: File not found at '{os.path.abspath(filepath)}'. Cannot update key.{Style.RESET_ALL}")
        return False

    updated_lines = []
    key_found = False

    # --- THIS IS THE FIX: Specify UTF-8 encoding for reading ---
    try:
        with open(filepath, "r", encoding='utf-8') as file:
            for line in file:
                # Use strip() and lower() for a case-insensitive, whitespace-agnostic check
                if line.strip().lower().startswith(prefix.lower()):
                    # A more robust regex to replace the value within quotes
                    updated_lines.append(re.sub(r'(".*?")', f'"{new_key}"', line, 1))
                    key_found = True
                else:
                    updated_lines.append(line)
    except Exception as e:
        print(f"{Fore.RED}❌ Error reading {filepath}: {e}{Style.RESET_ALL}")
        return False
    # -----------------------------------------------

    if not key_found:
        print(f"{Fore.YELLOW}⚠️  Warning: No line starting with '{prefix}' found in '{filepath}'. Key was not updated.{Style.RESET_ALL}")
        return False

    # --- THIS IS THE FIX: Specify UTF-8 encoding for writing ---
    with open(filepath, "w", encoding='utf-8') as file:
        file.writelines(updated_lines)
    # ------------------------------------------------------------

    print(f"✅ Key successfully updated in '{filepath}'.")
    return True

def update_env_with_timestamp(filepath, new_key):
    """Updates the .env file, adding a timestamp for auditability."""
    if not os.path.exists(filepath):
        with open(filepath, "w", encoding='utf-8') as file:
            pass # Create empty file

    updated_lines = []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(filepath, "r", encoding='utf-8') as file:
        for line in file:
            if "Key updated automatically on" in line or line.strip().startswith("API_KEY="):
                continue
            updated_lines.append(line)

    updated_lines.insert(0, f'# Key updated automatically on {timestamp}\n')
    updated_lines.insert(1, f'API_KEY="{new_key}"\n')

    with open(filepath, "w", encoding='utf-8') as file:
        file.writelines(updated_lines)
    print(f"✅ Key successfully updated in '{filepath}'.")


if __name__ == "__main__":
    colorama_init(autoreset=True)
    
    print(f"{Style.BRIGHT}--- 🔄 Starting Fully Automated API Key Sync ---")
    new_api_key = generate_api_key()
    print(f"🔑 Generated new key: {new_api_key}")

    update_env_with_timestamp(ENV_FILE_PATH, new_api_key)
    
    # --- THIS IS THE CORRECTION ---
    # The prefix now correctly targets the placeholder variable in the client file.
    update_file_key(CLIENT_FILE_PATH, new_api_key, "API_KEY_PLACEHOLDER =")

    print(f"\n{Style.BRIGHT}-------------------------------------------------")
    print(f"✅ Sync complete. Server and client now use the same key.")
    print(f"-------------------------------------------------")

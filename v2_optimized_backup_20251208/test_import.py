
import sys
import os

print(f"Current CWD: {os.getcwd()}")
print(f"Sys Path: {sys.path}")

try:
    import ai_provider
    print("✅ Imported ai_provider successfully")
except ImportError as e:
    print(f"❌ Failed to import ai_provider: {e}")
except Exception as e:
    print(f"❌ Error importing ai_provider: {e}")

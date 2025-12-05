
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from v2_optimized.config import get_config

try:
    from vnai.ai.provider import AIProvider, AIConfig
    print("✅ vnai imported successfully")
except ImportError as e:
    print(f"❌ Failed to import vnai: {e}")
    sys.exit(1)

def test_ai():
    config = get_config()
    provider, key = config.get_ai_provider()
    
    print(f"Provider: {provider}")
    print(f"Key: {key[:5]}..." if key else "Key: None")
    
    if not key:
        print("❌ No API key found")
        return

    try:
        ai_config = AIConfig(
            provider=provider,
            api_key=key,
            max_tokens=100,
            system_prompt="You are a helpful assistant."
        )
        ai = AIProvider(ai_config)
        print("🤖 Sending request to AI...")
        response = ai.chat("Hello, are you working?")
        print(f"✅ Response: {response}")
    except Exception as e:
        print(f"❌ AI Error: {e}")

if __name__ == "__main__":
    test_ai()

#!/usr/bin/env python
"""Test Ollama integration from Django app."""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'materalleapp.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from materalleapp.agent_base import get_llm_backend, get_anthropic_response

def test_ollama():
    print("Testing Ollama integration...")
    print(f"Current LLM Backend: {get_llm_backend()}")

    test_message = "Hello! What is 2+2?"
    print(f"\nSending message: {test_message}")

    try:
        response = get_anthropic_response(
            messages=[{"role": "user", "content": test_message}],
            system_prompt="You are a helpful math assistant. Answer concisely."
        )
        print(f"✅ Success! Response:\n{response}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_ollama()
    sys.exit(0 if success else 1)

"""Hello test: send 'hello' to the LLM from .env and print the reply."""
import os

from src.llm import chat

if __name__ == "__main__":
    print(f"Asking {os.environ['LLM_MODEL']} at {os.environ['LLM_BASE_URL']} ...")
    print("Reply:", chat([{"role": "user", "content": "Say hello in one short sentence."}]))

#!/usr/bin/env python
"""Quick test of the Modal proxy"""
import requests
import json

print("Testing Modal GPU proxy...")
response = requests.post(
    "http://localhost:11435/api/generate",
    json={
        "model": "qwen2.5-coder:7b",
        "prompt": "What is trail braking in F1? Answer in one sentence.",
        "stream": False,
        "options": {"temperature": 0.1}
    },
    timeout=120
)

print(f"Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"Response: {data.get('response', 'N/A')[:200]}")
    print("✅ GPU inference working!")
else:
    print(f"Error: {response.text}")

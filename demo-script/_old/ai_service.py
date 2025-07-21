import os
import sys
from dotenv import load_dotenv
import requests
import aiohttp
import json
import asyncio
import base64

load_dotenv()

OLLAMA_API_URL = os.getenv("OLLAMA_API_URL")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")
BRIDGE_API_CLIENT_ID = os.getenv("BRIDGE_API_CLIENT_ID")
BRIDGE_API_CLIENT_SECRET = os.getenv("BRIDGE_API_CLIENT_SECRET")
BRIDGE_API_APP_KEY = os.getenv("BRIDGE_API_APP_KEY")

async def bridge_it_auth():
    auth_string = f"{BRIDGE_API_CLIENT_ID}:{BRIDGE_API_CLIENT_SECRET}"
    encoded_auth = base64.b64encode(auth_string.encode()).decode()

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {encoded_auth}"
    }

    payload = {'grant_type': 'client_credentials'}

    url = "https://id.cisco.com/oauth2/default/v1/token"

    try:
        response = requests.post(url, data=payload, headers=headers)
        response.raise_for_status()
        return response.json()['access_token']
    except Exception as e:
        print("Failed to authenticate with BridgeIT:", e)
        sys.exit(1)


def call_bridgeIt(prompt):
    access_token = asyncio.run(bridge_it_auth())
    try:
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a chatbot"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "user": json.dumps({"appkey": BRIDGE_API_APP_KEY}),
            "stop": ["<|im_end|>"],
            "temperature": 1,
            "top_p": 0.25
        }
        
        headers = {
            "api-key": access_token,
            "Content-Type": "application/json"
        }

        url = "https://chat-ai.cisco.com/openai/deployments/gpt-4o-mini/chat/completions"
        response = requests.post(url, headers=headers, data=json.dumps(payload))

        content = response.json()["choices"][0]["message"]["content"]
        return content

    except requests.exceptions.RequestException as e:
        print(f"❌ BridgeIt API error: {e}")
        return None
    except (KeyError, IndexError, TypeError) as e:
        print("❌ Failed to extract message content from response.")
        print("🔍 Error details:", str(e))
        print("📦 Full response:", response.text)
        return None
    except Exception as e:
        print(f"❌ Unexpected error in call_bridgeIt: {e}")
        return None

def call_ollama(prompt):
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False
        }
        headers = {"Content-Type": "application/json"}

        response = requests.post(OLLAMA_API_URL, json=payload, headers=headers)
        response.raise_for_status()

        data = response.json()
        if "response" in data:
            return data["response"]
        else:
            print("❌ Unexpected response format:", data)
            return None

    except requests.exceptions.RequestException as e:
        print(f"❌ Ollama API error: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error in call_llm: {e}")
        return None
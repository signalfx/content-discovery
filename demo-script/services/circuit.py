import os
import requests

class CircuitClient:
    def __init__(self):
        self.client_id = os.getenv("CIRCUIT_CLIENT_ID")
        self.client_secret = os.getenv("CIRCUIT_CLIENT_SECRET")
        self.app_key = os.getenv("CIRCUIT_APP_KEY")
        
        if not all([self.client_id, self.client_secret, self.app_key]):
            raise ValueError("Missing one or more required environment variables.")

        self.token_url = "https://id.cisco.com/oauth2/default/v1/token"
        self.chat_url = "https://chat-ai.cisco.com/openai/deployments/gpt-4.1/chat/completions"
        self.token = self.get_access_token()

    def get_access_token(self) -> str:
        headers = {
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        response = requests.post(self.token_url, headers=headers, data=data)
        response.raise_for_status()
        token = response.json().get("access_token")
        return token

    def call_circuit(self, user_prompt: str, system_prompt: str) -> str:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "api-key": self.token
        }
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            "user": "{\"appkey\": \"egai-prd-ther-123212428-newcontent-1748250106657\"}",
            "stop": ["<|im_end|>"]
        }

        response = requests.post(self.chat_url, headers=headers, json=payload)
        
        if response.status_code != 200:
            print("Error response:\n", response.text)
            response.raise_for_status()

        return response.json()["choices"][0]["message"]["content"]
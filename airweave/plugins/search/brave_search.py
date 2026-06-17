import requests
import os

class BraveSearchPlugin:
    """
    Brave Search Plugin for Airweave.
    Enables agents to retrieve real-time web context via Brave Search API.
    """
    def __init__(self):
        self.api_key = os.getenv("BRAVE_API_KEY")
        self.base_url = "https://api.search.brave.com/res/v1/web/search"

    def search(self, query, count=5):
        headers = {"Accept": "application/json", "X-Subscription-Token": self.api_key}
        params = {"q": query, "count": count}
        response = requests.get(self.base_url, headers=headers, params=params)
        return response.json()

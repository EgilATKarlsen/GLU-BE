from typing import Dict, Any
import httpx
from app.config import settings
from .types.clerk import User


class ClerkClient:
    def __init__(self):
        self.secret_key = settings.CLERK_SECRET_KEY
        self.base_url = "https://api.clerk.com/v1"
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.secret_key}",
                "Content-Type": "application/json",
            },
        )

    async def get_user(self, user_id: str) -> User:
        """Fetch user details from Clerk"""
        response = await self.client.get(f"/users/{user_id}")
        print(response.json())
        response.raise_for_status()
        return User.model_validate(response.json())

    async def get_user_oauth_access_token(self, user_id: str, provider: str) -> Dict:
        """Get OAuth access tokens for a specific provider"""
        response = await self.client.get(
            f"/users/{user_id}/oauth_access_tokens/{provider}"
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # Log the error details for further debugging
            error_detail = exc.response.text
            print(f"Error fetching OAuth token: {error_detail}")
            raise
        return response.json()

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

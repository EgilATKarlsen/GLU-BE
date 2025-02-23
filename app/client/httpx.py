import httpx
from typing import Any, Dict, Optional
from contextlib import asynccontextmanager
import asyncio
from app.client.logger import logger


class ToolHttpClient:
    def __init__(self, client: httpx.AsyncClient, schema: dict, api_key: str):
        self._client = client
        self._schema = schema
        self._api_key = api_key

    async def send_tool_call(self, tool_name: str, tool_args: dict):
        with logger.span("send_tool_call"):
            tool = [item for item in self._schema if item["name"] == tool_name]
            if not tool:
                raise ValueError(
                    f"Tool {tool_name} not found in schema {self._schema[0]['name']}"
                )

            method = tool[0]["method"]
            path = tool[0]["path"]
            tool_config = None

            if tool_args.get("configuration", None):
                tool_config = tool_args.get("configuration")
                tool_args["body"] = tool_args.get("body", {}).get(tool_config, None)
                tool_args["query"] = tool_args.get("query", {}).get(tool_config, None)

            body = None
            query = None
            for key, value in tool_args.items():
                if key != "query" and key != "body":
                    path = path.replace("{" + key + "}", str(value))
                elif key == "query" and value:  # Only process if value is not empty
                    query_items = {
                        k: (
                            self._api_key
                            if v == "YOUR_AUTH_TOKEN"
                            else ",".join(map(str, v))
                            if isinstance(v, (list, tuple))
                            else str(v)
                        )
                        for k, v in value.items()
                        if v not in (None, "", {}, [])  # Skip empty values
                    }
                    if query_items:  # Only set query if there are non-empty items
                        query = query_items
                elif key == "body" and value:  # Only process if value is not empty
                    body_items = {
                        k: v for k, v in value.items() if v not in (None, "", {}, [])
                    }
                    if body_items:  # Only set body if there are non-empty items
                        body = body_items

            # Build the request object first
            request = self._client.build_request(
                method, path, json=body, params=query, headers=self._client.headers
            )

            logger.info(
                "Outgoing request details",
                method=request.method,
                url=str(request.url),
                headers=dict(request.headers),
                body=body if body else None,
            )

            # Send the request
            response: httpx.Response = await self._client.send(request)

            try:
                response_data = response.json()
                logger.info(f"Response details: {response_data}")

                if 200 <= response.status_code < 300:  # Check for any 2XX status code
                    return response_data
                else:
                    return {"status": "error", "message": response.text}
            except ValueError as e:  # This catches JSON decode errors
                logger.error(f"Failed to parse JSON response: {response.text}")
                if 200 <= response.status_code < 300:
                    return {"status": "success", "message": "empty response"}
                return {
                    "status": "error",
                    "message": f"Invalid JSON response: {response.text or '<empty response>'}",
                }

    async def close(self):
        await self._client.aclose()
        self._client = None
        logger.info("HTTP Client connection closed")


class HttpClient:
    def __init__(self, base_url: str = "", api_key: str = "", schema: dict = {}):
        # Ensure base_url includes a valid protocol. If not, default to "http://"
        if base_url and not (
            base_url.startswith("http://") or base_url.startswith("https://")
        ):
            base_url = "http://" + base_url

        self.base_url = base_url.rstrip("/")
        self._default_headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json; charset=utf-8",
        }
        self.schema = schema
        self._api_key = api_key
        self._client = None
        self._lock = asyncio.Lock()
        logger.info("HTTP Client initialized")

    async def get_client(self):
        async with self._lock:
            if self._client is None:
                self._client = httpx.AsyncClient(
                    base_url=self.base_url,
                    headers=self._default_headers,
                    timeout=30.0,  # Default timeout
                )
                logger.debug("Created new HTTP client connection")
            return self._client

    @asynccontextmanager
    async def get_session(self):
        try:
            client = ToolHttpClient(
                client=await self.get_client(),
                schema=self.schema,
                api_key=self._api_key,
            )
            yield client
        finally:
            pass

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> httpx.Response:
        """
        Perform an HTTP request with the configured client.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            path: URL path to append to base_url
            params: Query parameters
            json: JSON body data
            data: Form data
            headers: Additional headers to merge with defaults
            timeout: Request timeout in seconds
        """
        path = path.lstrip("/")
        merged_headers = {**self._default_headers, **(headers or {})}

        async with self.get_session() as client:
            try:
                response = await client.request(
                    method=method,
                    url=path,
                    params=params,
                    json=json,
                    data=data,
                    headers=merged_headers,
                    timeout=timeout,
                )
                response.raise_for_status()
                return response
            except httpx.HTTPError as e:
                logger.error(f"HTTP request failed: {str(e)}")
                raise

    async def cleanup(self):
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("HTTP Client connection closed")

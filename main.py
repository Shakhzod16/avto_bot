"""Start the FastAPI application and its lifespan-managed Telegram bot."""

import uvicorn

from backend.app.core.config import API_BIND_ADDRESS

if __name__ == "__main__":
    uvicorn.run(
        "backend.app.main:app",
        host=API_BIND_ADDRESS,
        port=8000,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )

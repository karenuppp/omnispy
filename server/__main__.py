"""Server entry point."""

import uvicorn

from .config import server_settings


def main():
    uvicorn.run(
        "server.app:create_app",
        host=server_settings.http_host,
        port=server_settings.http_port,
        factory=True,
        reload=True,
    )


if __name__ == "__main__":
    main()

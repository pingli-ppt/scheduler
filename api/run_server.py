"""使用环境变量中的端口启动果初 API，供本地运行和部署平台调用。"""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    port_text = os.environ.get("PORT", "8000")
    try:
        port = int(port_text)
    except ValueError as exc:
        raise SystemExit("PORT 必须是整数") from exc
    if port < 1 or port > 65535:
        raise SystemExit("PORT 必须在 1 到 65535 之间")

    uvicorn.run("api.main:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()

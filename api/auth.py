"""内部测试环境的网页登录认证与签名会话。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import subprocess
import time
from html import escape
from pathlib import Path


AUTH_ENABLED_ENV = "GUOCHU_AUTH_ENABLED"
HTPASSWD_PATH_ENV = "GUOCHU_HTPASSWD_PATH"
AUTH_USERNAME_ENV = "GUOCHU_AUTH_USERNAME"
SESSION_SECRET_ENV = "GUOCHU_SESSION_SECRET"
SESSION_SECRET_PATH_ENV = "GUOCHU_SESSION_SECRET_PATH"
SESSION_MAX_AGE_ENV = "GUOCHU_SESSION_MAX_AGE_SECONDS"
SESSION_COOKIE_NAME = "guochu_session"


def auth_enabled() -> bool:
    """仅在部署环境明确开启时启用认证，避免影响本地开发和既有测试。"""

    value = os.environ.get(AUTH_ENABLED_ENV, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def session_max_age() -> int:
    """返回会话有效期，限制在 5 分钟至 30 天之间。"""

    configured = os.environ.get(SESSION_MAX_AGE_ENV, "604800")
    try:
        value = int(configured)
    except ValueError as exc:
        raise RuntimeError(f"{SESSION_MAX_AGE_ENV} 必须是整数") from exc
    if not 300 <= value <= 2_592_000:
        raise RuntimeError(f"{SESSION_MAX_AGE_ENV} 必须在 300 到 2592000 之间")
    return value


def safe_redirect_path(value: str | None) -> str:
    """只允许站内绝对路径，避免登录后跳转到外部网站。"""

    if not value or not value.startswith("/") or value.startswith("//"):
        return "/"
    return value


def verify_platform_password(password: str) -> bool:
    """通过服务器本地 htpasswd 工具校验密码，不把密码放入命令行。"""

    if not password or len(password) > 256 or "\n" in password or "\r" in password:
        return False
    path = _htpasswd_path()
    username = os.environ.get(AUTH_USERNAME_ENV, "guochu").strip()
    if not username:
        raise RuntimeError(f"{AUTH_USERNAME_ENV} 不能为空")
    try:
        result = subprocess.run(
            ["htpasswd", "-v", str(path), username],
            input=f"{password}\n",
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def issue_session_token() -> str:
    """签发包含过期时间和密码文件版本的防篡改会话令牌。"""

    payload = {
        "sub": os.environ.get(AUTH_USERNAME_ENV, "guochu").strip(),
        "exp": int(time.time()) + session_max_age(),
        "v": _credential_version(),
    }
    encoded = _encode(
        json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    )
    signature = hmac.new(_session_secret(), encoded.encode("ascii"), hashlib.sha256)
    return f"{encoded}.{_encode(signature.digest())}"


def session_token_is_valid(token: str | None) -> bool:
    """验证签名、过期时间、用户和当前密码文件版本。"""

    if not token or len(token) > 2048:
        return False
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected_signature = hmac.new(
            _session_secret(), encoded.encode("ascii"), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(_decode(supplied_signature), expected_signature):
            return False
        payload = json.loads(_decode(encoded))
        if not isinstance(payload, dict):
            return False
        if int(payload.get("exp", 0)) < int(time.time()):
            return False
        if payload.get("sub") != os.environ.get(AUTH_USERNAME_ENV, "guochu").strip():
            return False
        return hmac.compare_digest(str(payload.get("v", "")), _credential_version())
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        return False


def login_page(next_path: str = "/") -> str:
    """返回不依赖外部资源的中文登录页，兼容微信内置浏览器。"""

    safe_next = escape(safe_redirect_path(next_path), quote=True)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
  <meta name="robots" content="noindex,nofollow">
  <title>果初内部测试登录</title>
  <style>
    :root {{ color-scheme: light; font-family: system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; min-height: 100vh; display: grid; place-items: center; padding: 24px; background: #f6f7f3; color: #243126; }}
    main {{ width: min(100%, 420px); padding: 32px 28px; border-radius: 24px; background: #fff; box-shadow: 0 18px 60px rgba(39,61,43,.12); }}
    .mark {{ width: 48px; height: 48px; display: grid; place-items: center; border-radius: 15px; background: #eaf4df; color: #41672e; font-size: 25px; }}
    h1 {{ margin: 18px 0 8px; font-size: 26px; }}
    p {{ margin: 0 0 24px; color: #667067; line-height: 1.65; }}
    label {{ display: block; margin-bottom: 8px; font-weight: 650; }}
    input {{ width: 100%; min-height: 50px; padding: 0 14px; border: 1px solid #cfd8ce; border-radius: 13px; font: inherit; }}
    input:focus {{ outline: 3px solid #dcebcf; border-color: #66894f; }}
    button {{ width: 100%; min-height: 50px; margin-top: 16px; border: 0; border-radius: 13px; background: #486f35; color: #fff; font: inherit; font-weight: 700; }}
    button:disabled {{ opacity: .65; }}
    #message {{ min-height: 24px; margin: 12px 0 0; color: #a53a32; font-size: 14px; }}
    small {{ display: block; margin-top: 20px; color: #7b837c; line-height: 1.6; }}
  </style>
</head>
<body>
  <main>
    <div class="mark" aria-hidden="true">芽</div>
    <h1>果初内部测试</h1>
    <p>请输入团队共享的访问密码。当前环境仅用于假数据测试。</p>
    <form id="login-form">
      <label for="password">访问密码</label>
      <input id="password" name="password" type="password" autocomplete="current-password" required autofocus>
      <button id="submit" type="submit">进入测试环境</button>
      <div id="message" role="alert" aria-live="polite"></div>
    </form>
    <small>登录状态仅保存在当前浏览器中，请勿在公共设备上保存密码。</small>
  </main>
  <script>
    const form = document.querySelector("#login-form");
    const button = document.querySelector("#submit");
    const message = document.querySelector("#message");
    form.addEventListener("submit", async (event) => {{
      event.preventDefault();
      button.disabled = true;
      message.textContent = "正在验证…";
      try {{
        const response = await fetch("/auth/login", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ password: form.password.value, next: "{safe_next}" }}),
        }});
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "密码不正确");
        window.location.replace(data.redirect || "/");
      }} catch (error) {{
        message.textContent = error.message || "登录失败，请稍后重试";
        button.disabled = false;
        form.password.select();
      }}
    }});
  </script>
</body>
</html>"""


def _htpasswd_path() -> Path:
    configured = os.environ.get(HTPASSWD_PATH_ENV)
    if not configured:
        raise RuntimeError(f"启用认证时必须设置 {HTPASSWD_PATH_ENV}")
    path = Path(configured)
    if not path.is_file():
        raise RuntimeError(f"找不到密码文件：{path}")
    return path


def _session_secret() -> bytes:
    direct = os.environ.get(SESSION_SECRET_ENV)
    if direct is not None:
        secret = direct.encode("utf-8")
    else:
        configured = os.environ.get(SESSION_SECRET_PATH_ENV)
        if not configured:
            raise RuntimeError(
                f"启用认证时必须设置 {SESSION_SECRET_ENV} 或 {SESSION_SECRET_PATH_ENV}"
            )
        secret = Path(configured).read_bytes().strip()
    if len(secret) < 32:
        raise RuntimeError("会话签名密钥至少需要 32 字节")
    return secret


def _credential_version() -> str:
    return hashlib.sha256(_htpasswd_path().read_bytes()).hexdigest()[:24]


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from api.main import _cors_origins
from api.run_server import main


class DeploymentEntryPointTests(unittest.TestCase):
    def test_cors_origins_are_read_from_environment(self) -> None:
        with patch.dict(
            os.environ,
            {"GUOCHU_CORS_ORIGINS": "https://h5.example.com, https://admin.example.com/"},
        ):
            self.assertEqual(
                _cors_origins(),
                ["https://h5.example.com", "https://admin.example.com"],
            )

    def test_server_uses_platform_port_and_public_host(self) -> None:
        with patch.dict(os.environ, {"PORT": "9123"}), patch(
            "api.run_server.uvicorn.run"
        ) as run:
            main()
        run.assert_called_once_with("api.main:app", host="0.0.0.0", port=9123)

    def test_invalid_port_is_rejected(self) -> None:
        with patch.dict(os.environ, {"PORT": "invalid"}), self.assertRaises(SystemExit):
            main()


if __name__ == "__main__":
    unittest.main()

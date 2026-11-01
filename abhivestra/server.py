"""Local HTTP API and static asset server."""

from __future__ import annotations

import csv
import io
import json
import logging
import mimetypes
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from .financial import ModelInputError, to_json_value
from .service import (
    RequestError,
    create_scenario,
    create_workspace,
    get_workspace,
    save_investment,
    update_assumption,
    update_scenario_override,
)
from .storage import Store, WorkspaceConflict


LOGGER = logging.getLogger("abhivestra")
WEB_ROOT = Path(__file__).resolve().parent.parent / "web"


def csv_text(value: str) -> str:
    if value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


class ApplicationHandler(BaseHTTPRequestHandler):
    server_version = "AbhiVestra/0.1"
    store = Store()

    def log_message(self, format_string: str, *args: object) -> None:
        LOGGER.info("%s - %s", self.address_string(), format_string % args)

    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(to_json_value(payload), separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise RequestError("Invalid Content-Length.")
        if length < 1 or length > 65536:
            raise RequestError("Request body must be between 1 byte and 64 KB.")
        if "application/json" not in self.headers.get("Content-Type", ""):
            raise RequestError("Content-Type must be application/json.")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise RequestError("Request body must contain valid JSON.")
        if not isinstance(payload, dict):
            raise RequestError("JSON request body must be an object.")
        return payload

    def _error(self, status: int, code: str, message: str) -> None:
        self._json(status, {"error": {"code": code, "message": message}})

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/v1/health":
            self._json(200, {"status": "ok", "storage": "sqlite"})
            return
        if path == "/api/v1/workspace":
            try:
                self._json(200, get_workspace(self.store))
            except ModelInputError as error:
                self._error(422, "model_input_error", str(error))
            except Exception:
                LOGGER.exception("Failed to load workspace")
                self._error(500, "internal_error", "Unable to load the workspace.")
            return
        if path == "/api/v1/export.csv":
            self._export_csv()
            return
        self._static(path)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            payload = self._body()
            if path == "/api/v1/workspace":
                self._json(201, create_workspace(self.store, payload))
            elif path == "/api/v1/scenarios":
                self._json(201, create_scenario(self.store, payload))
            elif path == "/api/v1/investment":
                self._json(200, save_investment(self.store, payload))
            else:
                self._error(404, "not_found", "API endpoint not found.")
        except RequestError as error:
            self._error(400, "validation_error", str(error))
        except WorkspaceConflict as error:
            self._error(409, "conflict", str(error))
        except ModelInputError as error:
            self._error(422, "model_input_error", str(error))
        except Exception:
            LOGGER.exception("Request failed")
            self._error(500, "internal_error", "The request could not be completed.")

    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        try:
            payload = self._body()
            assumption_match = re.fullmatch(r"/api/v1/assumptions/([a-z_]+)", path)
            override_match = re.fullmatch(
                r"/api/v1/scenarios/(\d+)/overrides/([a-z_]+)", path
            )
            if assumption_match:
                self._json(
                    200,
                    update_assumption(self.store, assumption_match.group(1), payload),
                )
            elif override_match:
                self._json(
                    200,
                    update_scenario_override(
                        self.store,
                        int(override_match.group(1)),
                        override_match.group(2),
                        payload,
                    ),
                )
            else:
                self._error(404, "not_found", "API endpoint not found.")
        except KeyError as error:
            self._error(404, "not_found", str(error).strip("'"))
        except RequestError as error:
            self._error(400, "validation_error", str(error))
        except ModelInputError as error:
            self._error(422, "model_input_error", str(error))
        except Exception:
            LOGGER.exception("Request failed")
            self._error(500, "internal_error", "The request could not be completed.")

    def _export_csv(self) -> None:
        try:
            data = get_workspace(self.store)["workspace"]
            if data is None or not data["models"]:
                self._error(404, "no_plan", "Create a workspace before exporting a forecast.")
                return
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(
                [
                    "Company",
                    csv_text(data["company_name"]),
                    "Scenario",
                    csv_text(data["models"][0]["scenario_name"]),
                ]
            )
            writer.writerow(
                [
                    "Period", "Revenue", "COGS", "Gross profit", "Operating expenses",
                    "EBITDA", "Net income", "Opening cash", "Net cash movement", "Closing cash",
                ]
            )
            for row in data["models"][0]["periods"]:
                writer.writerow(
                    [
                        row["period"], row["revenue"], row["cogs"], row["gross_profit"],
                        row["operating_expenses"], row["ebitda"], row["net_income"],
                        row["opening_cash"], row["net_cash_movement"], row["closing_cash"],
                    ]
                )
            body = buffer.getvalue().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header(
                "Content-Disposition", 'attachment; filename="abhivestra-forecast.csv"'
            )
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            LOGGER.exception("CSV export failed")
            self._error(500, "export_error", "The forecast export could not be generated.")

    def _static(self, path: str) -> None:
        relative = "index.html" if path in ("", "/") else unquote(path.lstrip("/"))
        if relative not in ("index.html", "app.js", "styles.css"):
            self._error(404, "not_found", "Page not found.")
            return
        file_path = WEB_ROOT / relative
        try:
            body = file_path.read_bytes()
        except OSError:
            self._error(404, "not_found", "Page not found.")
            return
        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)


def serve() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    host = os.environ.get("ABHIVESTRA_HOST", "127.0.0.1")
    port = int(os.environ.get("ABHIVESTRA_PORT", "8000"))
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise RuntimeError("The built-in server is local-only; do not bind it to a public interface.")
    server = ThreadingHTTPServer((host, port), ApplicationHandler)
    LOGGER.info("AbhiVestra listening at http://%s:%d", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Shutting down")
    finally:
        server.server_close()

#!/bin/env python3
import os
import json
import logging
import ssl
import time
import uuid

import requests
import tenacity
import urllib3
import websocket
from lxml import html

# we are using self-signed certificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))

MIN = 60
RETRY_WAIT = 5
RETRY_STOP_AFTER = 5 * MIN


class JupyterHubClientError(RuntimeError):
    pass


@tenacity.retry(
    retry=tenacity.retry_if_exception_type(JupyterHubClientError),
    wait=tenacity.wait_fixed(RETRY_WAIT),
    stop=tenacity.stop_after_delay(RETRY_STOP_AFTER),
    reraise=True,
)
def _returns_json(fun):
    def wrapper(*args, **kwargs):
        ret = fun(*args, **kwargs)
        if hasattr(args[0], "log"):
            logger = args[0].log
        else:
            logger = logging.getLogger(__name__)
        if not (200 <= ret.status_code < 300):
            logger.error(f"Call returned error: {ret.status_code}")
            logger.error(f"With content: {ret.content}")
        if not ret.content.decode():
            return {}
        try:
            return ret.json()
        except json.JSONDecodeError:
            logger.error("Unable to parse answer from server:")
            logger.error(f"{ret.content}")
            return None
        msg = "Unable to read JSON answer from server"
        logger.error(msg)
        raise JupyterHubClientError(msg)

    return wrapper


def timeit(name):
    def _timeit(fun):
        def wrapper(*args, **kwargs):
            if hasattr(args[0], "log"):
                logger = args[0].log
            else:
                logger = logging.getLogger(__name__)
            start = time.monotonic()
            ret = fun(*args, **kwargs)
            end = time.monotonic()
            logger.info(f"{name}:{end-start}")
        return wrapper
    return _timeit


def kernel_interrupt(session_id, ws):
    message = {
        "header": {
            "username": "",
            "version": "5.0",
            "session": session_id,
            "msg_id": uuid.uuid4().hex,
            "msg_type": "interrupt_request",
        },
        "content": {},
        "parent_header": {},
        "channel": "control",
        "metadata": {},
        "buffers": {},
    }
    ws.send(json.dumps(message))
    time.sleep(5)


class JupyterHubClient:
    def __init__(self, username: str, password: str, timeout: int = 10, server: str = "https://localhost:8000") -> None:

        self.log = logging.getLogger(type(self).__name__)

        self.username = username
        self.password = password
        self.timeout = timeout
        self.server = server
        self.session = None

    @timeit("login")
    def login(self) -> bool:

        # JupyterHub starts lab for us, so we might need to retry
        for _ in range(self.timeout):

            sess = requests.Session()

            try:
                req = sess.post(
                    f"{self.server}/hub/login",
                    verify=False,
                    data={"username": self.username, "password": self.password},
                )

            except (ConnectionRefusedError, requests.exceptions.ConnectionError) as exc:
                self.log.error(f"Error occured while connecting to Jupyter: {exc}")
                time.sleep(1)
                continue

            tree = html.fromstring(req.content)

            try:
                config_str = tree.xpath('//script[@id="jupyter-config-data"]/text()')[0].strip()
                break
            except IndexError:
                if "spawn-pending" not in req.url:
                    self.log.error("JupyterHub did not start JupyterLab")
                    time.sleep(1)
                    continue
            except:  # noqa
                msg = f"User {self.username} unable to login"
                self.log.error(msg)
                raise JupyterHubClientError(msg)

            time.sleep(1)

        else:
            msg = f"Timeout reached connecting to JupyterHub for user {self.username}"
            self.log.error(msg)
            raise JupyterHubClientError(msg)

        try:
            config = json.loads(config_str)
        except json.JSONDecodeError:
            self.log.error("JupyterHub did not return config")
            return False

        if "token" not in config:
            self.log.error("Unable to find token in config")
            return False

        self.token = config["token"]

        self.session = sess

        for cookie in self.session.cookies:
            if cookie.name == "_xsrf":
                self.session.headers.update({"X-XSRFToken": cookie.value})

        return True

    @timeit("stop_server")
    def stop_server(self):
        url = f"{self.server}/hub/api/users/{self.username}/server"
        referer = f"{self.server}/hub/home"
        _ = requests.delete(url, verify=False, headers={"referer": referer}, cookies=self.session.cookies)

    @timeit("get_running_kernel_list")
    @_returns_json
    def get_running_kernel_list(self):
        url = f"{self.server}/user/{self.username}/api/kernels"
        req = self.session.get(url, verify=False)
        return req

    @timeit("get_kernelspec_list")
    @_returns_json
    def get_kernelspec_list(self):
        url = f"{self.server}/user/{self.username}/api/kernelspecs"
        req = self.session.get(url, verify=False)
        return req

    @_returns_json
    def start_console(self, kernel_name, console_name="Console"):
        url = f"{self.server}/user/{self.username}/api/sessions"
        data = {
            "kernel": {"name": kernel_name},
            "name": console_name,
            "path": f"/{console_name.lower().replace(' ', '-')}-{uuid.uuid4()}",
            "type": "console",
        }
        req = self.session.post(url, verify=False, data=json.dumps(data))
        return req

    @timeit("list_sessions")
    @_returns_json
    def list_sessions(self):
        url = f"{self.server}/user/{self.username}/api/sessions"
        req = self.session.get(url, verify=False)
        return req

    @_returns_json
    def stop_session(self, session_uid):
        url = f"{self.server}/user/{self.username}/api/sessions/{session_uid}"
        req = self.session.delete(url, verify=False)
        return req

    @tenacity.retry(
        retry=tenacity.retry_if_exception_type(JupyterHubClientError),
        wait=tenacity.wait_fixed(RETRY_WAIT),
        stop=tenacity.stop_after_delay(RETRY_STOP_AFTER),
        reraise=True,
    )
    def run_command(self, code, kernel_id, session_id, timeout=10):
        ws_url = f"{self.server.replace('http', 'ws')}"
        ws_url += f"/user/{self.username}/api/kernels/{kernel_id}"
        ws_url += f"/channels?session_id={session_id}&token={self.token}"
        ws = websocket.create_connection(ws_url, sslopt={"cert_reqs": ssl.CERT_NONE}, timeout=timeout)
        time.sleep(0.1)  # try to avoid race-condition/timeout when run locally
        msg_id = uuid.uuid4().hex
        message = {
            "header": {
                "username": "",
                "version": "5.0",
                "session": session_id,
                "msg_id": msg_id,
                "msg_type": "execute_request",
            },
            "parent_header": {},
            "channel": "shell",
            "content": {
                "code": code,
                "silent": False,
                "store_history": False,
                "user_expressions": {},
                "allow_stdin": True,
            },
            "metadata": {},
            "buffers": {},
        }
        ws.send(json.dumps(message))
        messages = []
        status = "UNKN"
        result = "UNKN"

        time_start = time.monotonic()
        cell_process_timeot = MIN  # 1 minute

        while status == "UNKN" or result == "UNKN":
            time_now = time.monotonic()
            if time_now - time_start > cell_process_timeot:
                msg = f"Cell processed our command more that {cell_process_timeot} sec. Interrupting"
                self.log.error(msg)
                kernel_interrupt(session_id, ws)
                raise JupyterHubClientError(msg)
            try:
                msg = json.loads(ws.recv())
            except websocket.WebSocketTimeoutException:
                msg = "Timeout occurred while listening for websocket"
                self.log.error(msg)
                raise JupyterHubClientError(msg)
            self.log.info(f"Message from kernel received:\n{msg}")
            messages.append(msg)
            if msg["msg_type"] == "status":
                continue
            if msg["msg_type"] == "execute_input":
                # we don't know what to do with it
                continue
            if msg["msg_type"] == "execute_reply":
                status = msg["content"]["status"]
                continue
            if msg["msg_type"] == "error":
                self.log.error(f"Received error message: {msg}")
                result = "\n".join(msg["content"]["traceback"])
            if msg["msg_type"] == "stream":
                if result == "UNKN":
                    result = msg["content"]["text"]
                else:
                    result += msg["content"]["text"]
        ws.close()

        return status, result

    @timeit("call_cmdaemon")
    @_returns_json
    def call_cmdaemon(self, message):
        url = f"{self.server}/user/{self.username}/cmdaemon_proxy"
        req = self.session.post(url, verify=False, data=json.dumps(message))
        return req

    @timeit("cm_kc_module_list")
    @_returns_json
    def cm_kc_module_list(self, loaded_modules=None):
        if loaded_modules is None:
            loaded_modules = []
        url = f"{self.server}/user/{self.username}/kernelcreator/envmodules"
        req = self.session.get(url, verify=False, params={'load': loaded_modules})
        return req

    @timeit("cm_kc_list_templates")
    @_returns_json
    def cm_kc_list_templates(self):
        url = f"{self.server}/user/{self.username}/kernelcreator/templates"
        req = self.session.get(url, verify=False)
        return req

    @_returns_json
    def cm_kc_get_template(self, template_name):
        url = f"{self.server}/user/{self.username}"
        url += f"/kernelcreator/templates/{template_name}"
        req = self.session.get(url, verify=False)
        return req

    @timeit("cm_kc_list_kernels")
    @_returns_json
    def cm_kc_list_kernels(self):
        url = f"{self.server}/user/{self.username}/kernelcreator/kernels"
        req = self.session.get(url, verify=False)
        return req

    @_returns_json
    def cm_kc_delete_kernel(self, kernel_name):
        url = f"{self.server}/user/{self.username}"
        url += f"/kernelcreator/kernels/{kernel_name}"
        req = self.session.delete(url, verify=False)
        return req

    @_returns_json
    def cm_kc_create_kernel(self, template_name, kernel_name, values):
        url = f"{self.server}/user/{self.username}/kernelcreator"
        url += f"/kernels/{kernel_name}/create"
        data = {"values": values, "template": template_name}
        req = self.session.put(url, verify=False, data=json.dumps(data))
        return req

    @_returns_json
    def cm_vnc_get_pass(self, kernel_id):
        url = f"{self.server}/user/{self.username}/kernelvnc/{kernel_id}"
        req = self.session.get(url, verify=False)
        return req

    @_returns_json
    def cm_vnc_start(
        self,
        kernel_id,
        vnc_starter_options=None,
        additional_monitor_options=None,
    ):
        if vnc_starter_options is None:
            vnc_starter_options = ""
        if additional_monitor_options is None:
            additional_monitor_options = ""
        url = f"{self.server}/user/{self.username}/kernelvnc/{kernel_id}"
        data = {
            "vnc_starter_options": vnc_starter_options,
            "additional_monitor_options": additional_monitor_options,
        }
        req = self.session.put(url, verify=False, data=json.dumps(data))
        return req

    @_returns_json
    def cm_vnc_stop(self, kernel_id):
        url = f"{self.server}/user/{self.username}/kernelvnc/{kernel_id}"
        req = self.session.delete(url, verify=False)
        return req

    @tenacity.retry(
        retry=tenacity.retry_if_exception_type(JupyterHubClientError),
        wait=tenacity.wait_fixed(RETRY_WAIT),
        stop=tenacity.stop_after_delay(RETRY_STOP_AFTER),
        reraise=True,
    )
    def cm_vnc_ws_get(self, kernel_id, timeout=10):
        url = f"{self.server.replace('http', 'ws')}"
        url += f"/user/{self.username}/kernelvnc/"
        url += f"{kernel_id}/ws?token={self.token}"
        ws = websocket.create_connection(
            url,
            sslopt={"cert_reqs": ssl.CERT_NONE},
            timeout=timeout,
        )
        try:
            return ws.recv()
        except websocket.WebSocketProtocolException as exc:
            self.log.error(exc)
            raise JupyterHubClientError(exc)

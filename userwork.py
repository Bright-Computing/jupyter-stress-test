import os
import sys
import time
import random
from jupyterhub_client import JupyterHubClient, JupyterHubClientError

def main():
    try:
        username = sys.argv[1]
    except IndexError:
        username = None
    try:
        server = sys.argv[2]
    except IndexError:
        server = "https://localhost:8000"
    password = os.getenv("BM_USERPASS")
    if not username or not password:
        sys.exit(1)

    jhl = JupyterHubClient(username=username, password=password, server=server)
    time.sleep(random.uniform(0,3))
    try:
        jhl.login()
    except JupyterHubClientError:
        jhl.log.info("login:timeout")
        sys.exit(1)

    for _ in range(10):
        try:
            jhl.list_sessions()
        except JupyterHubClientError:
            jhl.log.info("list_sessions:timeout")
        try:
            jhl.get_kernelspec_list()
        except JupyterHubClientError:
            jhl.log.info("get_kernelspec_list:timeout")
        try:
            jhl.get_running_kernel_list()
        except JupyterHubClientError:
            jhl.log.info("get_running_kernel_list:timeout")
        try:
            jhl.call_cmdaemon({"service": "cmmain", "call": "ping"})
        except JupyterHubClientError:
            jhl.log.info("call_cmdaemon:timeout")
        try:
            jhl.cm_kc_list_templates()
        except JupyterHubClientError:
            jhl.log.info("cm_kc_list_templates:timeout")
        try:
            jhl.cm_kc_list_kernels()
        except JupyterHubClientError:
            jhl.log.info("cm_kc_list_kernels:timeout")
        try:
            jhl.cm_kc_module_list()
        except JupyterHubClientError:
            jhl.log.info("cm_kc_module_list:timeout")


if __name__ == "__main__":
    main()

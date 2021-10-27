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
    time.sleep(random.randint(0,5))
    try:
        jhl.login()
    except JupyterHubClientError:
        jhl.log.info("login:timeout")
        sys.exit(1)
    try:
        jhl.stop_server()
    except JupyterHubClientError:
        jhl.log.info("stop_server:timeout")


if __name__ == "__main__":
    main()

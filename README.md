# How to run

(100 users will be created)

```
./run sync HOST
ssh HOST
cd /root/jupyter-stress
./run prepare 500  # number of users to create
./run benchmark https://JUPYTER_HOST:8000 50 200
```

Where:
50 - number of users simultaneously trying to login
200 - number of login to existing sessions

To remove created users:

```
./run clear
```

# Tunables

/cm/local/apps/jupyter/current/conf/jupyterhub_config.py
c.Authenticator.delete_invalid_users = True

Or in `cmsh`

```
configurationoverlay
    -> use jupyterhub
    -> roles
    -> use jupyterhub
    -> configs
    -> add c.Authenticator.delete_invalid_users
    -> ..
    -> set c.authenticator.delete_invalid_users True
    -> commit
```

echo "EG_PORT_RETRIES=10000" >> /etc/default/jupyterhub-singleuser-gw

/usr/lib/systemd/system/cm-jupyterhub.service
LimitNOFILE=1048576

sysctl -w fs.file-max=209715200

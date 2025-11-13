import base64
import json

from kubespawner import KubeSpawner as OrigKubeSpawner
from traitlets import Bool
from traitlets import Callable
from traitlets import default
from traitlets import Dict
from traitlets import List
from traitlets import observe
from traitlets import Unicode
from traitlets import Union


class DataMountKubeSpawner(OrigKubeSpawner):
    data_mount_enabled = Bool(
        default_value=True,
        config=True,
        help="""
        Enable or Disable the JupyterLab DataMount extension.
        """,
    )

    enable_nfs_mounts = Bool(
        default_value=False,
        config=True,
        help="""
        Whether NFS mounts should be allowed in the backend. When using NFS Userhomes, users might be able to mount all userhomes.
        """,
    )

    blocked_nfs_mounts = List(
        default_value=[
            "10.0.0.0/8",
            "172.16.0.0/12",
            "192.168.0.0/16",
            "127.0.0.0/8",
            "169.254.0.0/16",
        ],
        config=True,
        help="""
        List of CIDR blocks for which NFS mounts are blocked.
        Administrators can configure multiple CIDRs to prevent users
        from mounting NFS shares from restricted networks.

        Example::

            c.KubeSpawner.blocked_nfs_mounts = [
                "10.0.0.0/8",
                "172.16.0.0/12",
                "192.168.0.0/16",
                "127.0.0.0/8",
                "169.254.0.0/16"
            ]

        Any NFS mount request originating from an IP address within
        these ranges will be denied.
        """,
    )

    templates = Union(
        trait_types=[List(), Callable()],
        default_value=[],
        config=True,
        help="""
    Configure which mount templates should be shown to the user. This also defines the order.
    """,
    )

    def get_templates(self):
        if callable(self.templates):
            return self.templates(self)
        return self.templates

    init_mounts = List(
        [],
        config=True,
        help="""
          List of dictionaries representing additional mounts to be added to the pod. 
          
          This may be a coroutine.

          Example::
          
            c.KubeSpawner.init_mounts = [
              {
                "path": "aws",
                "options": {
                "displayName": "AWS #1",
                "template": "aws",
                "config": {
                  "remotepath": "bucketname",
                  "type": "s3",
                  "provider": "AWS",
                  "access_key_id": "_id_",
                  "secret_access_key": "_secret_",
                  "region": "eu-north-1"
                }
                }
              },
              {
                "path": "b2drop",
                "options": {
                "displayName": "B2Drop",
                "template": "b2drop",
                "readonly": true,
                "config": {
                  "remotepath": "/",
                  "type": "webdav",
                  "url": "https://b2drop.eudat.eu/remote.php/dav/files/_user_/",
                  "vendor": "nextcloud",
                  "user": "_user_",
                  "obscure_pass": "_password_"
                }
              }
            ]
        """,
    )

    data_mount_extension_version = Unicode(
        None,
        allow_none=True,
        config=True,
        help="""
        Define the version of the JupyterLab Datamount Extension
        """,
    )

    data_mount_config = Unicode(
        None,
        allow_none=True,
        config=True,
        help="""
        Multiline String to define the configuration used from the jupyter
        notebook server.
        Used to configure the DataMount JupyterLab Extension.
        Will be added to $JUPYTER_CONFIG_PATH/jupyter_notebook_config.py
        """,
    )

    def data_mount_start_default(self):
        version = (
            f"=={self.data_mount_extension_version}"
            if self.data_mount_extension_version
            else ""
        )
        return """#!/bin/sh
if command -v pip >/dev/null 2>&1; then
    if [ -n "$VIRTUAL_ENV" ]; then
        pip install jupyterlab-data-mount{datamount_version}
    else
        pip install --user jupyterlab-data-mount{datamount_version}
    fi
fi
export JUPYTER_CONFIG_PATH="${JUPYTER_CONFIG_PATH:+$JUPYTER_CONFIG_PATH:}/mnt/datamount_start"
command -v start-singleuser.sh >/dev/null 2>&1 && exec start-singleuser.sh || exec jupyterhub-singleuser
""".replace(
            "{datamount_version}", version
        )

    def get_data_mount_start(self):
        if callable(self.data_mount_start):
            return self.data_mount_start(self)
        return self.data_mount_start

    data_mount_start = Union(
        trait_types=[Unicode(), Callable()],
        default_value=data_mount_start_default,
        allow_none=True,
        config=True,
        help="""
        Multiline String to define the start procedure used for the jupyter
        notebook server.
        """,
    )

    logging_config = Dict(
        None,
        allow_none=True,
        config=True,
        help="""
        Add logging handler to the DataMount sidecar container.
        Stream and File are enabled by default.
        Example::
        
          logging_config = {
            "stream": {
              "enabled": True,
              "level": 10,
              "formatter": "simple",
              "stream": "ext://sys.stdout",
            },
            "file": {
                "enabled": True,
                "level": 20,
                "filename": "/mnt/data_mounts/mount.log",
                "formatter": "simple_user", # simple_user, simple or json
                "when": "h",
                "interval": 1,
                "backupCount": 0,
                "encoding": None,
                "delay": false,
                "utc": false,
                "atTime": None,
                "errors": None,
            },
            "syslog": {
              "enabled": False,
              "level": 20,
              "formatter": "json",
              "address": ["ip", 5141],
              "facility": 1,
              "socktype": "ext://socket.SOCK_DGRAM",
            },
            "smtp": {
              "enabled": False,
              "level": 50,
              "formatter": "simple",
              "mailhost": "mailhost",
              "fromaddr": "smtpmail",
              "toaddrs": [],
              "subject": "SMTPHandler - Log",
              "secure": None,
              "timeout": 1,
            }
        }
      """,
    )

    def get_env(self):
        env = super().get_env()
        if self.data_mount_enabled:
            env["JUPYTERLAB_DATA_MOUNT_ENABLED"] = str(self.data_mount_enabled)
            env["JUPYTERLAB_DATA_MOUNT_DIR"] = self.data_mount_path
            templates = self.get_templates()
            if templates:
                env["JUPYTERLAB_DATA_MOUNT_TEMPLATES"] = ",".join(templates)
        return env

    def get_default_volumes(self):
        ret = {}
        if self.data_mount_enabled:
            ret = {
                "dm-data-mounts": {"name": "dm-data-mounts", "emptyDir": {}},
                "dm-mounts-config": {"name": "dm-mounts-config", "emptyDir": {}},
                "dm-mounts-start": {"name": "dm-mounts-start", "emptyDir": {}},
            }
        return ret

    @default("volumes")
    def _default_volumes(self):
        """Provide default volumes when none are set."""
        return self.get_default_volumes()

    @observe("volumes")
    def _ensure_default_volumes(self, change):
        try:
            new_volumes = change["new"]

            if self.data_mount_enabled:
                if isinstance(new_volumes, list):
                    try:
                        new_volumes = {c["name"]: c for c in new_volumes}
                    except:
                        self.log.error(
                            "Could not parse volumes list to dict, use empty dict instead"
                        )
                        new_volumes = {}

                default_volumes = self.get_default_volumes()
                if default_volumes:
                    for key, value in default_volumes.items():
                        if key not in new_volumes.keys():
                            new_volumes[key] = value

            self.volumes = new_volumes
        except Exception:
            self.log.exception("Ensure volumes failed")

    data_mount_path = Unicode(
        "/home/jovyan/data_mounts",
        config=True,
        help="Path to mount data in the notebook container",
    )

    def get_default_volume_mounts(self):
        ret = {}
        if self.data_mount_enabled:
            ret["dm-data-mounts"] = {
                "name": "dm-data-mounts",
                "mountPath": self.data_mount_path,
                "mountPropagation": "HostToContainer",
            }
            ret["dm-mounts-start"] = {
                "name": "dm-mounts-start",
                "mountPath": "/mnt/datamount_start",
                "readOnly": True,
            }
        return ret

    @default("volume_mounts")
    def _default_volumes_mounts(self):
        """Provide default volumes when none are set."""
        return self.get_default_volume_mounts()

    @observe("volume_mounts")
    def _ensure_default_volume_mounts(self, change):
        try:
            new_volume_mounts = change["new"]

            if self.data_mount_enabled:
                if isinstance(new_volume_mounts, list):
                    try:
                        new_volume_mounts = {c["name"]: c for c in new_volume_mounts}
                    except:
                        self.log.error(
                            "Could not parse volume_mounts list to dict, use empty dict instead"
                        )
                        new_volume_mounts = {}

                default_volume_mounts = self.get_default_volume_mounts()
                for key, value in default_volume_mounts.items():
                    if key not in new_volume_mounts.keys():
                        new_volume_mounts[key] = value

            self.volume_mounts = new_volume_mounts
        except Exception:
            self.log.exception("Ensure volume_mounts failed")

    data_mounts_image = Unicode(
        "jupyterjsc/jupyterlab-data-mount-api:latest",
        config=True,
        help="Image to use for the data mount container",
    )

    def _get_extra_data_mount_init_container(self):
        if self.data_mount_enabled:
            try:
                commands = ["apk add --no-cache coreutils"]

                if self.init_mounts:
                    mounts_b64 = base64.b64encode(
                        json.dumps(self.init_mounts).encode()
                    ).decode()
                    commands.append(
                        f"echo '{mounts_b64}' | base64 -d > /mnt/config/mounts.json"
                    )

                if self.logging_config:
                    logging_config_b64 = base64.b64encode(
                        json.dumps(self.logging_config).encode()
                    ).decode()
                    commands.append(
                        f"echo '{logging_config_b64}' | base64 -d > /mnt/config/logging.json"
                    )

                if self.data_mount_config:
                    data_mount_config_b64 = base64.b64encode(
                        self.data_mount_config.encode()
                    ).decode()
                    commands.append(
                        f"echo '{data_mount_config_b64}' | base64 -d > /mnt/datamount_start/jupyter_notebook_config.py"
                    )
                    commands.append(
                        f"echo '{data_mount_config_b64}' | base64 -d > /mnt/datamount_start/jupyter_server_config.py"
                    )

                data_mount_start_b64 = base64.b64encode(
                    self.get_data_mount_start().encode()
                ).decode()
                commands.append(
                    f"echo '{data_mount_start_b64}' | base64 -d > /mnt/datamount_start/datamount_start-singleuser.sh"
                )
                commands.append(
                    "chmod +x /mnt/datamount_start/datamount_start-singleuser.sh"
                )

                return {
                    "mounts-config": {
                        "image": "alpine:latest",
                        "imagePullPolicy": "Always",
                        "name": "mounts-config",
                        "volumeMounts": [
                            {
                                "name": "dm-mounts-config",
                                "mountPath": "/mnt/config",
                            },
                            {
                                "name": "dm-mounts-start",
                                "mountPath": "/mnt/datamount_start",
                            },
                        ],
                        "command": ["sh", "-c", " && ".join(commands)],
                    }
                }
            except Exception as e:
                self.log.exception("Could not set init Container")
                return {}
        else:
            return {}

    @default("init_containers")
    def _default_init_containers(self):
        """Provide default init containers when none are set."""
        return self._get_extra_data_mount_init_container()

    @observe("init_containers")
    def _ensure_default_init_containers(self, change):
        try:
            new_init_containers = change["new"]

            if self.data_mount_enabled:
                if isinstance(new_init_containers, list):
                    try:
                        new_init_containers = {
                            c["name"]: c for c in new_init_containers
                        }
                    except:
                        self.log.error(
                            "Could not parse init_containers list to dict, use empty dict instead"
                        )
                        new_init_containers = {}
                extra_data_mount_init_container = (
                    self._get_extra_data_mount_init_container()
                )
                for name, container in extra_data_mount_init_container.items():
                    if name not in new_init_containers.keys():
                        new_init_containers[name] = container

            self.init_containers = new_init_containers
        except Exception:
            self.log.exception("Ensure init_containers failed")

    def _get_extra_data_mount_container(self):
        extra_data_mount_container = {}
        if self.data_mount_enabled:
            volume_mounts = [
                {
                    "name": "dm-data-mounts",
                    "mountPath": "/mnt/data_mounts",
                    "mountPropagation": "Bidirectional",
                }
            ]
            if self.init_mounts:
                volume_mounts.append(
                    {
                        "name": "dm-mounts-config",
                        "mountPath": "/mnt/config/mounts.json",
                        "subPath": "mounts.json",
                    }
                )

            if self.logging_config:
                volume_mounts.append(
                    {
                        "name": "dm-mounts-config",
                        "mountPath": "/mnt/config/logging.json",
                        "subPath": "logging.json",
                    }
                )

            extra_data_mount_container = {
                "data-mounts": {
                    "image": self.data_mounts_image,
                    "imagePullPolicy": "Always",
                    "name": "data-mounts",
                    "volumeMounts": volume_mounts,
                    "env": [
                        {
                            "name": "NFS_ENABLED",
                            "value": "true" if self.enable_nfs_mounts else "false",
                        },
                        {
                            "name": "NFS_BLOCKED_MOUNTS",
                            "value": ",".join(self.blocked_nfs_mounts),
                        },
                    ],
                    "securityContext": {
                        "capabilities": {"add": ["SYS_ADMIN", "MKNOD", "SETFCAP"]},
                        "privileged": True,
                        "allowPrivilegeEscalation": True,
                    },
                }
            }
        return extra_data_mount_container

    @default("extra_containers")
    def _default_extra_containers(self):
        """Provide default volumes when none are set."""
        return self._get_extra_data_mount_container()

    @observe("extra_containers")
    def _ensure_default_extra_containers(self, change):
        try:
            new_extra_containers = change["new"]

            if self.data_mount_enabled:
                if isinstance(new_extra_containers, list):
                    try:
                        new_extra_containers = {
                            c["name"]: c for c in new_extra_containers
                        }
                    except:
                        self.log.error(
                            "Could not parse extra_containers list to dict, use empty dict instead"
                        )
                        new_extra_containers = {}
                extra_data_mount_container = self._get_extra_data_mount_container()

                for name, container in extra_data_mount_container.items():
                    if name not in new_extra_containers.keys():
                        new_extra_containers[name] = container

            self.extra_containers = new_extra_containers
        except Exception:
            self.log.exception("Ensure extra_containers failed")

    cmd = ["/mnt/datamount_start/datamount_start-singleuser.sh"]


# Implementation with the same name as the original class
# Allows for easier integration into the JupyterHub HelmChart
class KubeSpawner(DataMountKubeSpawner):
    pass

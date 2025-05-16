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
        Used to confiugre the DataMount JupyterLab Extension.
        Will be added to $JUPYTER_CONFIG_DIR/jupyter_notebook_config.py
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
        ret = []
        if self.data_mount_enabled:
            ret = [
                {"name": "data-mounts", "emptyDir": {}},
                {"name": "mounts-config", "emptyDir": {}},
            ]
        return ret

    @default("volumes")
    def _default_volumes(self):
        """Provide default volumes when none are set."""
        return self.get_default_volumes()

    @observe("volumes")
    def _ensure_default_volumes(self, change):
        try:
            new_volumes = change["new"]

            if isinstance(new_volumes, dict):
                new_volumes = [new_volumes]

            if self.data_mount_enabled:
                default_volumes = self.get_default_volumes()
                if default_volumes:
                    for v in default_volumes:
                        if v not in new_volumes:
                            new_volumes.append(v)

            self.volumes = new_volumes
        except Exception:
            self.log.exception("Ensure volumes failed")

    data_mount_path = Unicode(
        "/home/jovyan/data_mounts",
        config=True,
        help="Path to mount data in the notebook container",
    )

    def get_default_volume_mounts(self):
        if self.data_mount_enabled:
            return {
                "name": "data-mounts",
                "mountPath": self.data_mount_path,
                "mountPropagation": "HostToContainer",
            }
        else:
            return None

    @default("volume_mounts")
    def _default_volumes_mounts(self):
        """Provide default volumes when none are set."""
        ret = self.get_default_volume_mounts()
        if ret:
            return [ret]
        else:
            return []

    @observe("volume_mounts")
    def _ensure_default_volume_mounts(self, change):
        try:
            new_volume_mounts = change["new"]

            if isinstance(new_volume_mounts, dict):
                new_volume_mounts = [new_volume_mounts]

            if self.data_mount_enabled:
                default_volume_mounts = self.get_default_volume_mounts()
                if default_volume_mounts:
                    if isinstance(default_volume_mounts, dict):
                        default_volume_mounts = [default_volume_mounts]
                    for m in default_volume_mounts:
                        if m not in new_volume_mounts:
                            new_volume_mounts.append(m)

            self.volume_mounts = new_volume_mounts
        except Exception:
            self.log.exception("Ensure volume_mounts failed")

    data_mounts_image = Unicode(
        "jupyterjsc/jupyterlab-data-mount-api:latest",
        config=True,
        help="Image to use for the data mount container",
    )

    def _get_extra_data_mount_init_container(self):
        if (self.init_mounts or self.logging_config) and self.data_mount_enabled:
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

                return {
                    "image": "alpine:latest",
                    "imagePullPolicy": "Always",
                    "name": "mounts-config",
                    "volumeMounts": [
                        {
                            "name": "mounts-config",
                            "mountPath": "/mnt/config",
                        }
                    ],
                    "command": ["sh", "-c", " && ".join(commands)],
                }
            except Exception as e:
                self.log.exception("Could not set init Container")
                return None
        else:
            return None

    @default("init_containers")
    def _default_init_containers(self):
        """Provide default volumes when none are set."""
        ret = self._get_extra_data_mount_init_container()
        if ret:
            return [ret]
        else:
            return []

    @observe("init_containers")
    def _ensure_default_init_containers(self, change):
        try:
            new_init_containers = change["new"]

            if isinstance(new_init_containers, dict):
                new_init_containers = [new_init_containers]

            if self.data_mount_enabled:
                extra_data_mount_init_container = (
                    self._get_extra_data_mount_init_container()
                )
                if (
                    extra_data_mount_init_container
                    and extra_data_mount_init_container not in new_init_containers
                ):
                    new_init_containers.append(extra_data_mount_init_container)

            self.init_containers = new_init_containers
        except Exception:
            self.log.exception("Ensure init_containers failed")

    def _get_extra_data_mount_container(self):
        extra_data_mount_container = {}
        if self.data_mount_enabled:
            volume_mounts = [
                {
                    "name": "data-mounts",
                    "mountPath": "/mnt/data_mounts",
                    "mountPropagation": "Bidirectional",
                }
            ]
            if self.init_mounts:
                volume_mounts.append(
                    {
                        "name": "mounts-config",
                        "mountPath": "/mnt/config/mounts.json",
                        "subPath": "mounts.json",
                    }
                )

            if self.logging_config:
                volume_mounts.append(
                    {
                        "name": "mounts-config",
                        "mountPath": "/mnt/config/logging.json",
                        "subPath": "logging.json",
                    }
                )

            extra_data_mount_container = {
                "image": self.data_mounts_image,
                "imagePullPolicy": "Always",
                "name": "data-mounts",
                "volumeMounts": volume_mounts,
                "securityContext": {
                    "capabilities": {"add": ["SYS_ADMIN", "MKNOD", "SETFCAP"]},
                    "privileged": True,
                    "allowPrivilegeEscalation": True,
                },
            }
        return extra_data_mount_container

    @default("extra_containers")
    def _default_extra_containers(self):
        """Provide default volumes when none are set."""
        ret = self._get_extra_data_mount_container()
        if ret:
            return [ret]
        else:
            return []

    @observe("extra_containers")
    def _ensure_default_extra_containers(self, change):
        try:
            new_extra_containers = change["new"]

            if isinstance(new_extra_containers, dict):
                new_extra_containers = [new_extra_containers]

            if self.data_mount_enabled:
                extra_data_mount_container = self._get_extra_data_mount_container()

                if (
                    extra_data_mount_container
                    and extra_data_mount_container not in new_extra_containers
                ):
                    new_extra_containers.append(extra_data_mount_container)

            self.extra_containers = new_extra_containers
        except Exception:
            self.log.exception("Ensure extra_containers failed")

    @default("cmd")
    def _default_cmd(self):
        """Set the default command if none is provided."""
        base_cmd = ["sh", "-c"]

        if not self.data_mount_enabled:
            return base_cmd + [
                """
                if command -v start-singleuser.sh > /dev/null; then
                    exec start-singleuser.sh;
                else
                    exec jupyterhub-singleuser;
                fi
                """
            ]

        version = (
            f"=={self.data_mount_extension_version}"
            if self.data_mount_extension_version
            else ""
        )

        write_config_cmd = ""
        if self.data_mount_config:
            data_mount_config_b64 = base64.b64encode(
                self.data_mount_config.encode()
            ).decode()
            write_config_cmd = f"""
            mkdir -p /tmp/data_mount_config && \
            echo '{data_mount_config_b64}' | base64 -d > /tmp/data_mount_config/jupyter_notebook_config.py && \
            """

        full_cmd = f"""
            if command -v pip > /dev/null; then \
                pip install --user jupyterlab-data-mount{version}; \
            fi && \
            {write_config_cmd}
            export JUPYTER_CONFIG_PATH="${{JUPYTER_CONFIG_PATH:+$JUPYTER_CONFIG_PATH:}}/tmp/data_mount_config" && \
            if command -v start-singleuser.sh > /dev/null; then \
                exec start-singleuser.sh; \
            else \
                exec jupyterhub-singleuser; \
            fi
        """

        return base_cmd + [full_cmd]

    _setting_default_cmd = False

    @observe("cmd")
    def _ensure_pip_first(self, change):
        """Ensure 'pip install --user jupyterlab-data-mount' is prepended only if data_mount_enabled is True."""
        if self._setting_default_cmd:
            return

        self._setting_default_cmd = True
        new_cmd = change["new"]

        if new_cmd is None or not isinstance(new_cmd, list) or len(new_cmd) == 0:
            self.cmd = self._default_cmd()
        else:
            if self.data_mount_enabled:
                # Only prepend pip install if data_mount_enabled
                if len(new_cmd) >= 3 and new_cmd[0] == "sh" and new_cmd[1] == "-c":
                    existing_script = new_cmd[2]
                    combined_script = (
                        "pip install --user jupyterlab-data-mount && " + existing_script
                    )
                    self.cmd = ["sh", "-c", combined_script]
                else:
                    combined_script = (
                        "pip install --user jupyterlab-data-mount && "
                        + " ".join(new_cmd)
                    )
                    self.cmd = ["sh", "-c", combined_script]
            else:
                # data_mount_enabled is False — just set the command as is
                self.cmd = new_cmd


# Implementation with the same name as the original class
# Allows for easier integration into the JupyterHub HelmChart
class KubeSpawner(DataMountKubeSpawner):
    pass

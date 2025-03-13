import base64
import json

from kubespawner import KubeSpawner as OrigKubeSpawner
from traitlets import Callable
from traitlets import default
from traitlets import List
from traitlets import observe
from traitlets import Unicode
from traitlets import Union


class DataMountKubeSpawner(OrigKubeSpawner):
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
            "url": "https://b2drop.eudat.eu/remote.php/webdav/",
            "vendor": "nextcloud",
            "user": "_user_",
            "obscure_pass": "_password_"
          }
          }
        }
        ]
    """,
    ).tag(config=True)

    def get_env(self):
        env = super().get_env()
        env["JUPYTERLAB_DATA_MOUNT_ENABLED"] = "true"
        env["JUPYTERLAB_DATA_MOUNT_DIR"] = self.data_mount_path
        templates = self.get_templates()
        self.log.info("ABC")
        self.log.info(templates)
        if templates:
            env["JUPYTERLAB_DATA_MOUNT_TEMPLATES"] = ",".join(templates)
        return env

    def get_default_volumes(self):
        ret = [
            {"name": "data-mounts", "emptyDir": {}},
            {"name": "init-mounts", "emptyDir": {}},
        ]
        return ret

    @default("volumes")
    def _default_volumes(self):
        """Provide default volumes when none are set."""
        return self.get_default_volumes()

    @observe("volumes")
    def _ensure_default_volumes(self, change):
        new_volumes = change["new"]

        try:
            if isinstance(new_volumes, dict):
                new_volumes = [new_volumes]

            default_volumes = self.get_default_volumes()
            if default_volumes and default_volumes not in new_volumes:
                new_volumes.extend(default_volumes)

            self.log.info(f"volumes: {new_volumes}")
            self.volumes = new_volumes
        except:
            self.log.exception("wtf")

    data_mount_path = Unicode(
        "/home/jovyan/data_mounts",
        config=True,
        help="Path to mount data in the notebook container",
    )

    def get_default_volume_mounts(self):
        return {
            "name": "data-mounts",
            "mountPath": self.data_mount_path,
            "mountPropagation": "HostToContainer",
        }

    @default("volume_mounts")
    def _default_volumes_mounts(self):
        """Provide default volumes when none are set."""
        return [self.get_default_volume_mounts()]

    @observe("volume_mounts")
    def _ensure_default_volume_mounts(self, change):
        new_volume_mounts = change["new"]

        if isinstance(new_volume_mounts, dict):
            new_volume_mounts = [new_volume_mounts]

        default_volume_mounts = self.get_default_volume_mounts()

        if default_volume_mounts and default_volume_mounts not in new_volume_mounts:
            new_volume_mounts.append(default_volume_mounts)

        # self.log.info(f"volume_mounts: {new_volume_mounts}")
        self.volume_mounts = new_volume_mounts

    data_mounts_image = Unicode(
        "jupyterjsc/jupyterlab-data-mount-api:v0.1.4",
        config=True,
        help="Image to use for the data mount container",
    )

    def _get_extra_data_mount_init_container(self):
        if not self.init_mounts:
            return None
        try:
            mounts_b64 = base64.b64encode(
                json.dumps(self.init_mounts).encode()
            ).decode()
            return {
                "image": "alpine:latest",
                "imagePullPolicy": "Always",
                "name": "init-mounts",
                "volumeMounts": [
                    {
                        "name": "init-mounts",
                        "mountPath": "/mnt/init_mounts",
                    }
                ],
                "command": [
                    "sh",
                    "-c",
                    "apk add --no-cache coreutils && echo '%s' | base64 -d > /mnt/init_mounts/mounts.json"
                    % mounts_b64,
                ],
            }
        except Exception as e:
            self.log.exception("wtf")
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
        new_init_containers = change["new"]

        if isinstance(new_init_containers, dict):
            new_init_containers = [new_init_containers]

        extra_data_mount_init_container = self._get_extra_data_mount_init_container()

        if (
            extra_data_mount_init_container
            and extra_data_mount_init_container not in new_init_containers
        ):
            new_init_containers.append(extra_data_mount_init_container)

        # self.log.info(f"init_containers: {new_init_containers}")
        self.init_containers = new_init_containers

    def _get_extra_data_mount_container(self):
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
                    "name": "init-mounts",
                    "mountPath": "/mnt/init_mounts/mounts.json",
                    "subPath": "mounts.json",
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
        return [self._get_extra_data_mount_container()]

    @observe("extra_containers")
    def _ensure_default_extra_containers(self, change):
        new_extra_containers = change["new"]

        if isinstance(new_extra_containers, dict):
            new_extra_containers = [new_extra_containers]

        extra_data_mount_container = self._get_extra_data_mount_container()

        if (
            extra_data_mount_container
            and extra_data_mount_container not in new_extra_containers
        ):
            new_extra_containers.append(extra_data_mount_container)

        # self.log.info(f"extra_containers: {new_extra_containers}")
        self.extra_containers = new_extra_containers

    @default("cmd")
    def _default_cmd(self):
        """Set the default command if none is provided."""
        base_cmd = [
            "sh",
            "-c",
            "pip install --user jupyterlab-data-mount==0.1.5 && "
            "if command -v start-singleuser.sh > /dev/null; then exec start-singleuser.sh; else exec jupyterhub-singleuser; fi",
        ]

        return base_cmd

    _setting_default_cmd = False

    @observe("cmd")
    def _ensure_pip_first(self, change):
        """Ensure 'pip install --user jupyterlab-data-mount' is always prepended."""
        # Skip recursion if we are setting the default command
        if self._setting_default_cmd:
            return

        self._setting_default_cmd = True
        new_cmd = change["new"]

        # self.log.info(f"cmd: {new_cmd}")
        if new_cmd is None or not isinstance(new_cmd, list) or len(new_cmd) == 0:
            # Apply default if cmd is unset or empty
            self.cmd = self._default_cmd()
        else:
            # Otherwise, modify the existing command
            self.cmd = [
                "sh",
                "-c",
                f"pip install --user jupyterlab-data-mount && ({' '.join(new_cmd)})",
            ]


# Implementation with the same name as the original class
# Allows for easier integration into the JupyterHub HelmChart
class KubeSpawner(DataMountKubeSpawner):
    pass

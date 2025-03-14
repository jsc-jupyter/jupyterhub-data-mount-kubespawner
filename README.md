# JupyterHub DataMount KubeSpawner

[![Documentation](https://img.shields.io/badge/Documentation-passed-green)](https://jsc-jupyter.github.io/jupyterlab-data-mount/spawner/installation/)
[![PyPI](https://img.shields.io/badge/PyPI-passed-green)](https://pypi.org/project/jupyterhub-datamountspawner)
  
JupyterHub Spawner to start a JupyterLab using the [JupyterLab DataMount Extension](https://github.com/jsc-jupyter/jupyterlab-data-mount) extension.  

![JupyterLab](https://jsc-jupyter.github.io/jupyterlab-data-mount/images/jupyterlab.png)
  
## Installation

Example configuration for [Zero2JupyterHub](https://z2jh.jupyter.org/en/stable/):  

```yaml
hub:
  args:
    - -c
    - >-
      pip install jupyterhub-datamountspawner &&
      jupyterhub -f /usr/local/etc/jupyterhub/jupyterhub_config.py
  command:
    - /bin/bash
  extraConfig:
    customConfig: |
      c.JupyterHub.spawner_class = 'datamountspawner.KubeSpawner'
singleuser:
  image:
    name: jupyter/minimal-notebook
    tag: latest
  storage:
    type: none
```

Checkout [documentation](https://jsc-jupyter.github.io/jupyterlab-data-mount/spawner/installation/) for more.

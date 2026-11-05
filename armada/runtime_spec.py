"""Pinned Windows runtime shared by packaging and update compatibility checks.

The full Python patch is a security baseline. Updating it requires an installer;
an application-only update cannot replace Python or its bundled dependencies.
"""

PYTHON_VERSION = '3.14.10'
INSTALLER_BASELINE_VERSION = '0.99.124'
PYTHON_MINOR = '.'.join(PYTHON_VERSION.split('.')[:2])
PYTHON_ABI = PYTHON_MINOR.replace('.', '')
PYTHON_DLL = f'python{PYTHON_ABI}.dll'
PYTHON_PTH = f'python{PYTHON_ABI}._pth'
PYTHON_ZIP = f'python{PYTHON_ABI}.zip'
PYTHON_URL = f'https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip'
PYTHON_SHA256 = '90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159'
SBOM_URL = PYTHON_URL + '.spdx.json'
SBOM_SHA256 = 'd448c78f5fae170303d3b022d61507155e4d30e541c32bff3a4edd2b1e8dbf47'
# Hashes checked against python.org's 2026-10-25 release and upstream SPDX document.
RELEASE_URL = 'https://www.python.org/downloads/release/python-31410/'

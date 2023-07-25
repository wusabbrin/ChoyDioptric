# -*- coding: utf-8 -*-
"""
Functions, etc to be used mainly by other utils. If you're running into
a circular reference in utils, put the problem code here. 

Created September 10th, 2021

@author: mccambria
"""

import platform
from pathlib import Path
import socket
import json
from importlib import import_module
import sys
import labrad
import numpy as np


def get_config_module(pc_name=None):
    if pc_name is None:
        pc_name = socket.gethostname()
    module_name = f"config.{pc_name}"
    module = import_module(module_name)
    return module


def get_config_dict(pc_name=None):
    module = get_config_module(pc_name)
    return module.config


def get_default_email():
    config = get_config_dict()
    return config["default_email"]


def _get_os_config_val(key):
    os_name = platform.system()  # Windows or Linux
    os_name_lower = os_name.lower()
    config = get_config_dict()
    val = config[f"{os_name_lower}_{key}"]
    return val


def get_nvdata_path():
    """Returns an OS-dependent Path to the nvdata directory"""
    return _get_os_config_val("nvdata_path")


def get_repo_path():
    """Returns an OS-dependent Path to the repo directory"""
    return _get_os_config_val("repo_path")


def get_server(cxn, server_name):
    config = get_config_dict()
    dev_name = config["Servers"][server_name]
    return cxn[dev_name]


# region LabRAD registry utilities - mostly deprecated in favor of config file


def get_registry_entry(key, directory, cxn=None):
    """Get an entry from the LabRAD registry"""
    if cxn is None:
        with labrad.connect(username="", password="") as cxn:
            return _get_registry_entry_sub(key, directory, cxn)
    else:
        return _get_registry_entry_sub(key, directory, cxn)


def _get_registry_entry_sub(key, directory, cxn):
    p = cxn.registry.packet()
    p.cd("", *directory)
    p.get(key)
    return p.send()["get"]


def _labrad_get_config_dict(cxn=None):
    """Get the whole config from the registry as a dictionary"""
    if cxn is None:
        with labrad.connect() as cxn:
            return _labrad_get_config_dict_sub(cxn)
    else:
        return _labrad_get_config_dict_sub(cxn)


def _labrad_get_config_dict_sub(cxn):
    config_dict = {}
    _labrad_populate_config_dict(cxn, ["", "Config"], config_dict)
    return config_dict


def _labrad_populate_config_dict(cxn, reg_path, dict_to_populate):
    """Populate the config dictionary recursively"""

    # Sub-folders
    cxn.registry.cd(reg_path)
    sub_folders, keys = cxn.registry.dir()
    for el in sub_folders:
        sub_dict = {}
        sub_path = reg_path + [el]
        _labrad_populate_config_dict(cxn, sub_path, sub_dict)
        dict_to_populate[el] = sub_dict

    # Keys
    if len(keys) == 1:
        cxn.registry.cd(reg_path)
        p = cxn.registry.packet()
        key = keys[0]
        p.get(key)
        val = p.send()["get"]
        if type(val) == np.ndarray:
            val = val.tolist()
        dict_to_populate[key] = val

    elif len(keys) > 1:
        cxn.registry.cd(reg_path)
        p = cxn.registry.packet()
        for key in keys:
            p.get(key)
        vals = p.send()["get"]

        for ind in range(len(keys)):
            key = keys[ind]
            val = vals[ind]
            if type(val) == np.ndarray:
                val = val.tolist()
            dict_to_populate[key] = val


# endregion

if __name__ == "__main__":
    print(_labrad_get_config_dict())

# -*- coding: utf-8 -*-
"""
Functions, etc to be referenced only by other utils. If you're running into
a circular reference in utils, put the function or whatever here. 

Created September 10th, 2021

@author: mccambria
"""

import platform
from pathlib import Path
from functools import cache
import socket
import importlib
import time
import labrad
import numpy as np




def get_config_module(pc_name=None, reload=False):
    if pc_name is None:
        pc_name = socket.gethostname()
    pc_name = pc_name.lower()
    try:
        module_name = f"config.{pc_name}"
        module = importlib.import_module(module_name)
    except Exception:  # Fallback to the default
        module_name = "config.default"
        module = importlib.import_module(module_name)
    if reload:
        module = importlib.reload(module)

    return module


@cache
def get_config_dict(pc_name=None):
    module = get_config_module(pc_name)
    return module.config


@cache
def get_opx_config_dict(pc_name=None):
    module = get_config_module(pc_name)
    try:
        return module.opx_config
    except Exception as exc:
        return None
    
@cache
def _get_os_config_val(key):
    os_name_lower = platform.system().lower()  # windows or linux
    config = get_config_dict()
    val = config[f"{os_name_lower}_{key}"]
    return val

@cache
def get_repo_path():
    """Returns an OS-dependent Path to the repo directory"""
    return _get_os_config_val("repo_path")

@cache
def get_nvdata_path():
    """Returns an OS-dependent Path to the nvdata directory"""
    return _get_os_config_val("nvdata_path")

# def get_nvdata_dir():
#     """Returns an OS-dependent Path to the nvdata directory (configured above)"""
#     os_name = platform.system()
#     if os_name == "Windows":
#         nvdata_dir = windows_nvdata_dir
#     # elif os_name == "Linux":
#     #     nvdata_dir = linux_nvdata_dir

#     return nvdata_dir

@cache
def get_default_email():
    config = get_config_dict()
    return config["default_email"]

def get_registry_entry(cxn, key, directory):
    """Return the value for the specified key. Directory as a list,
    where an empty string indicates the top of the registry
    """

    p = cxn.registry.packet()
    p.cd("", *directory)
    p.get(key)
    return p.send()["get"]

def get_server(cxn, server_type):
    """Helper function for server getters in tool_belt. Return None if we can't
    make the connection for whatever reason (e.g. the key does not exist in 
    the registry
    """
    try:
        server_name = get_registry_entry(cxn, server_type, ["", "Config", "Servers"])
        server = getattr(cxn, server_name)
    except Exception as exc:
        # print(f"Could not get server type {server_type}")
        server = None
    return server
# @cache
# def get_server(server_key):
#     server_name = get_server_name(server_key)
#     if server_name is None:
#         return None
#     else:
#         cxn = labrad_connect()
#         return cxn[server_name]
    
@cache
def get_server_name(server_key):
    config = get_config_dict()
    confg_servers = config["Servers"]
    if server_key not in confg_servers:
        return None
    server_name = confg_servers[server_key]
    return server_name

def labrad_connect():
    """Return a labrad connection with default username and password"""
    global global_cxn
    if global_cxn is None:
        global_cxn = labrad.connect(username="", password="")
    return global_cxn

if __name__ == "__main__":
    start = time.time()
    for ind in range(1000):
        get_config_dict()
    stop = time.time()
    print(stop - start)
# -*- coding: utf-8 -*-
"""
Tools for managing our experimental database

Created November 15th, 2023

@author: mccambria
"""

# region Imports and constants

from io import BytesIO
from datetime import datetime
import os
import time
from utils import common
from utils import _cloud
from pathlib import Path
import ujson  # usjson is faster than standard json library
import orjson  # orjson is faster and more lightweight than ujson, but can't write straight to file
from git import Repo
from enum import Enum
import numpy as np
import socket
import labrad
import copy
from utils.constants import *  # Star import is bad practice, but useful here for json deescape

data_manager_folder = common.get_data_manager_folder()


# endregion
# region Save functions


def get_time_stamp():
    """Get a formatted timestamp for file names and metadata.

    Returns:
        string: <year>_<month>_<day>-<hour>_<minute>_<second>
    """

    timestamp = str(datetime.now())
    timestamp = timestamp.split(".")[0]  # Keep up to seconds
    timestamp = timestamp.replace(":", "_")  # Replace colon with dash
    timestamp = timestamp.replace("-", "_")  # Replace dash with underscore
    timestamp = timestamp.replace(" ", "-")  # Replace space with dash
    return timestamp


def get_file_path(source_file, time_stamp, name, subfolder=None):
    """Get the file path to save to. This will be in a subdirectory of nvdata

    Parameters
    ----------
    source_file : string
        Source __file__ of the caller which will be parsed to get the
        name of the subdirectory we will write to
    time_stamp : string
        Formatted timestamp to include in the file name
    name : string
        The full file name consists of <timestamp>_<name>.<ext>
        Ext is supplied by the save functions
    subfolder : string, optional
        Subfolder to save to under file name, by default None

    Returns
    -------
    Path
        Path to save to
    """

    pc_name = socket.gethostname()
    branch_name = _get_branch_name()
    source_name = Path(source_file).stem
    date_folder = "_".join(time_stamp.split("_")[0:2])  # yyyy_mm

    folder_path = Path(f"pc_{pc_name}/branch_{branch_name}/{source_name}/{date_folder}")

    if subfolder is not None:
        folder_path = folder_path / subfolder

    file_name = f"{time_stamp}-{name}"

    return folder_path / file_name


def save_figure(fig, file_path):
    """Save a matplotlib figure as a svg.

    Params:
        fig: matplotlib.figure.Figure
            The figure to save
        file_path: string
            The file path to save to including the file name, excluding the
            extension
    """

    # Write to bytes then upload that to the cloud
    file_path_svg = file_path.with_suffix(".svg")
    content = BytesIO()
    fig.savefig(content, format="svg")
    _cloud.upload(file_path_svg, content)


def save_raw_data(raw_data, file_path, keys_to_compress=None):
    """Save raw data in the form of a dictionary to a text file. New lines
    will be printed between entries in the dictionary.

    Params:
        raw_data: dict
            The raw data as a dictionary - will be saved via JSON
        file_path: string
            The file path to save to including the file name, excluding the
            extension
        keys_to_compress: list(string)
            Keys to values in raw_data that we want to extract and save to
            a separate compressed file. Currently supports numpy arrays
    """

    start = time.time()
    file_path_txt = file_path.with_suffix(".txt")

    # Work with a copy of the raw data to avoid mutation
    raw_data = copy.deepcopy(raw_data)

    # Compress numpy arrays to linked file
    if keys_to_compress is not None:
        # Build the object to compress
        kwargs = {}
        for key in keys_to_compress:
            kwargs[key] = raw_data[key]
        # Upload to cloud
        content = BytesIO()
        np.savez_compressed(content, **kwargs)
        file_path_npz = file_path.with_suffix(".npz")
        npz_file_id = _cloud.upload(file_path_npz, content)
        # Replace the value in the raw data with a string that tells us where
        # to find the compressed file
        for key in keys_to_compress:
            raw_data[key] = f"{npz_file_id}.npz"

    # Always include the config dict
    config = common.get_config_dict()
    config_copy = copy.deepcopy(config)
    _json_escape(config_copy)
    raw_data["config"] = config_copy

    # And the OPX config dict if there is one
    opx_config = common.get_opx_config_dict()
    if opx_config is not None:
        opx_config_copy = copy.deepcopy(opx_config)
        _json_escape(opx_config_copy)
        raw_data["opx_config"] = opx_config_copy

    # Upload raw data to the cloud
    option = orjson.OPT_INDENT_2 | orjson.OPT_SERIALIZE_NUMPY
    content = orjson.dumps(raw_data, option=option)
    _cloud.upload(file_path_txt, content)

    stop = time.time()
    print(stop - start)


# endregion
# region Load functions


def get_raw_data(file_name=None, file_id=None, use_cache=True):
    """Returns a dictionary containing the json object from the specified
    raw data file

    Parameters
    ----------
    file_name : str, optional
        Name of the raw data file to load, w/o extension. If file_name is passed,
        file_id is None, and the file is not in the cache, then we'll identify
        the proper file by searching the cloud for it. By default None
    file_id : str, optional
        Cloud ID of the file to load. Loaded directly from the cloud or cache, no
        search necessary. By default None
    use_cache : bool, optional
        Whether or not to use the cache. If True, we'll try to pull the file from
        the cache - if it's not there already we'll add it to the cache. Otherwise
        we'll get the file straight from the cloud and skip caching it. By default
        True

    Returns
    -------
    dict
        Dictionary containing the json object from the specified raw data file
    """

    if file_id is not None:
        file_id = str(file_id)

    ### Check the cache first

    # Try to open an existing cache manifest
    retrieved_from_cache = False
    if use_cache:
        try:
            with open(data_manager_folder / "cache_manifest.txt") as f:
                cache_manifest = ujson.load(f)
        except Exception as exc:
            cache_manifest = None

        # Try to open the cached file
        try:
            id_name_table = cache_manifest["id_name_table"]
            if file_id is not None:
                file_name = id_name_table[file_id]
            with open(data_manager_folder / f"{file_name}.txt", "rb") as f:
                file_content = f.read()
            data = orjson.loads(file_content)
            retrieved_from_cache = True
        except Exception as exc:
            retrieved_from_cache = False

    ### If not in cache, download from the cloud

    if not use_cache or not retrieved_from_cache:
        # Download the base file
        file_content, file_id, file_name = _cloud.download(file_name, "txt", file_id)
        data = orjson.loads(file_content)

        # Find and decompress the linked numpy arrays
        for key in data:
            val = data[key]
            if not isinstance(val, str):
                continue
            val_split = val.split(".")
            if val_split[-1] != "npz":
                continue
            first_part = val_split[0]
            npz_file_id = first_part if first_part else None
            npz_file_content, _, _ = _cloud.download(file_name, "npz", npz_file_id)
            npz_data = np.load(BytesIO(npz_file_content))
            data |= npz_data
            break

    ### Add to cache and return the data

    # Update the cache manifest
    if use_cache:
        cache_manifest_updated = False
        if cache_manifest is None:
            cache_manifest = {
                "id_name_table": {file_id: file_name},
                "cached_file_ids": [file_id],
            }
            cache_manifest_updated = True
        elif not retrieved_from_cache:
            id_name_table = cache_manifest["id_name_table"]
            cached_file_ids = cache_manifest["cached_file_ids"]
            # Add the new file to the manifest
            if not retrieved_from_cache:
                id_name_table[file_id] = file_name
                cached_file_ids.append(file_id)
            while len(cached_file_ids) > 10:
                file_id_to_remove = cached_file_ids.pop(0)
                file_name_to_remove = id_name_table[file_id_to_remove]
                id_name_table.remove(file_id_to_remove)
                os.remove(data_manager_folder / f"{file_name_to_remove}.txt")
            cache_manifest = {
                "id_name_table": id_name_table,
                "cached_file_ids": cached_file_ids,
            }
            cache_manifest_updated = True
        if cache_manifest_updated:
            with open(data_manager_folder / "cache_manifest.txt", "w") as f:
                ujson.dump(cache_manifest, f, indent=2)

        # Write the actual data file to the cache
        if not retrieved_from_cache:
            file_content = orjson.dumps(data, option=orjson.OPT_SERIALIZE_NUMPY)
            with open(data_manager_folder / f"{file_name}.txt", "wb") as f:
                f.write(file_content)

    return data


# endregion
# region Misc public functions


def get_time_stamp_from_file_name(file_name):
    """Get the formatted timestamp from a file name

    Returns:
        string: <year>_<month>_<day>-<hour>_<minute>_<second>
    """

    file_name_split = file_name.split("-")
    time_stamp_parts = file_name_split[0:2]
    timestamp = "-".join(time_stamp_parts)
    return timestamp


def utc_from_file_name(file_name, time_zone="CST"):
    # First 19 characters are human-readable timestamp
    date_time_str = file_name[0:19]
    # Assume timezone is CST
    date_time_str += f"-{time_zone}"
    date_time = datetime.strptime(date_time_str, r"%Y_%m_%d-%H_%M_%S-%Z")
    timestamp = date_time.timestamp()
    return timestamp


def get_nv_sig_units_no_cxn():
    with labrad.connect() as cxn:
        nv_sig_units = get_nv_sig_units(cxn)
    return nv_sig_units


def get_nv_sig_units():
    try:
        config = common.get_config_dict()
        nv_sig_units = config["nv_sig_units"]
    except Exception:
        nv_sig_units = ""
    return nv_sig_units


# endregion
# region Private functions


def _get_branch_name():
    """Return the name of the active branch of dioptric"""
    repo_path = common.get_repo_path()
    repo = Repo(repo_path)
    return repo.active_branch.name


def _json_escape(raw_data):
    """Recursively escape a raw data object for JSON. Slow, so use sparingly"""

    # See what kind of loop we need to do through the object
    if isinstance(raw_data, dict):
        # Just get the original keys
        keys = list(raw_data.keys())
    elif isinstance(raw_data, list):
        keys = range(len(raw_data))

    for key in keys:
        val = raw_data[key]

        # Escape the value
        if isinstance(val, Path):
            raw_data[key] = str(val)
        elif isinstance(val, type):
            raw_data[key] = str(val)

        # Recursion for dictionaries and lists
        elif isinstance(val, dict) or isinstance(val, list):
            _json_escape(val)


# endregion


if __name__ == "__main__":
    time_stamp = get_time_stamp()
    file_path = get_file_path(__file__, time_stamp, "MCCTEST")
    data = {"matt": "Cambria!"}
    save_raw_data(data, file_path)

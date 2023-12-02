import os

from yaml import load, dump

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


def load_config_from_file(file_path):
    with open(file_path, "r") as f:
        return load(f, Loader)


def save_config_to_file(dict_file, file_path):
    with open(file_path, "w") as f:
        return dump(dict_file, f, Dumper)

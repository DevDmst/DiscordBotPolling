import datetime
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


def convert_datetime_to_formatted_timestamp(date_time: datetime.datetime):
    return f"<t:{date_time.timestamp()}:f>"


def convert_formatted_timestamp_to_datetime(timestamp: str):
    timestamp = timestamp[3:-3]
    return datetime.datetime.fromtimestamp(timestamp)

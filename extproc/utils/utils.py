from os.path import expandvars
from typing import Dict

from flatten_json import flatten, unflatten_list


def dict_env_sub(data: Dict, separator: str = ".") -> Dict:
    return unflatten_list({k: expandvars(v) for k, v in flatten(data).items()})

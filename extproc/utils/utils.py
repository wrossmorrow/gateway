from os.path import expandvars as _expandvars
from typing import Dict, Union

from flatten_json import flatten, unflatten_list


def dict_env_sub(data: Dict, separator: str = ".") -> Dict:
    return unflatten_list({k: expandvars(v) for k, v in flatten(data).items()})


def expandvars(val: Union[str, bytes, int, bool]) -> Union[str, bytes, int, bool]:
    if isinstance(val, str):
        return _expandvars(val)
    elif isinstance(val, bytes):
        return _expandvars(val)
    return val

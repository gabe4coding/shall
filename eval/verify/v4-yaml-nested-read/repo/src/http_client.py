import yaml
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

settings = yaml.safe_load(open("config/app.yaml"))


def adapter() -> HTTPAdapter:
    conf = settings["http"]["client"]
    retry = Retry(total=conf["retries"], backoff_factor=conf["backoff_seconds"], backoff_jitter=0.3,
                  allowed_methods=frozenset({"GET", "PUT", "DELETE"}))
    return HTTPAdapter(max_retries=retry)

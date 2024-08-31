import os
import re
from collections import defaultdict

import requests

PEERS_REPO = "../peers-wg"


def read_repo_keys(directory):
    repokeys = defaultdict(list)
    for file in os.scandir(directory):
        if file.is_file():
            filename = os.fsdecode(file)
            with open(filename) as keyfile:
                key = keyfile.readline().strip()
                if not re.match("^[0-9a-zA-Z+/]{42}[AEIMQUYcgkosw480]=$", key):
                    print(f"Warning: Skipping {filename}. Key is invalid!")
                    continue
                router_name = filename.lstrip(directory)
                repokeys[key].append(router_name)
    return repokeys


keys = read_repo_keys(PEERS_REPO)
duplicates = {k: v for k, v in keys.items() if len(v) > 1}

url = "https://map.aachen.freifunk.net/data/nodes.json"
t = requests.get(url)
t.raise_for_status()
nodes = t.json()["nodes"]
# Parse the key data and create a TSIG keyring
pairs = []

router_names = {}
for node in nodes:
    nodeinfo = node["nodeinfo"]
    try:
        public_key: str = nodeinfo["software"]["wireguard"]["public_key"]
    except KeyError:
        continue

    router_names[public_key] = nodeinfo["hostname"]


for key, dups in duplicates.items():
    name = router_names.get(key)
    if name:
        print(set(dups) - set([name]))
    else:
        print("failed", key)

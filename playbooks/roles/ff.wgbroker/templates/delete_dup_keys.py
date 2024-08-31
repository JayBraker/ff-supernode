import os
import pwd
import re
import subprocess
from time import sleep
from contextlib import contextmanager
from collections import defaultdict
from pathlib import Path

import requests

REPO = "/etc/wireguard/peers-wg"
LOCKFILE = ".broker.lock"
NODES_URL = "https://map.aachen.freifunk.net/data/nodes.json"
WG_PUBKEY_PATTERN = re.compile(r"^[A-Za-z0-9+/]{42}[AEIMQUYcgkosw480]=$")

@contextmanager
def lock():
    # Code to acquire resource, e.g.:
    lockfile = Path(REPO)/LOCKFILE
    while lockfile.is_file():
        sleep(5)
    lockfile.touch()
    try:
        yield
    finally:
        lockfile.unlink()

def demote(user_uid, user_gid):
    def result():
        print(f"{user_uid}:{user_gid}")
        os.setgid(user_gid)
        os.setuid(user_uid)
    return result

def execute_autouser(cmd):
    # WARNING this is NOT threadsafe.
    autouser='auto'
    pw_record = pwd.getpwnam(autouser)
    homedir = pw_record.pw_dir
    user_uid = pw_record.pw_uid
    user_gid = pw_record.pw_gid
    env = os.environ.copy()
    env.update({'HOME': homedir, 'LOGNAME': autouser, 'USER': autouser})

    s = subprocess.Popen([cmd], shell=True, env=env,
                         preexec_fn=demote(user_uid, user_gid), stdout=subprocess.PIPE)
    s.wait()

def push_repo():
    execute_autouser(f"git -C {REPO} push")

def pull_repo():
    execute_autouser(f"git -C {REPO} pull")

def commit_repo(filename):
    execute_autouser(f"git -C {REPO} add {REPO}/{filename}")
    execute_autouser(f'git -C {REPO} commit -m "auto remove old duplicate key: {filename}"')

def read_repo_keys(directory) -> dict[str, list[Path]]:
    repokeys = defaultdict(list)
    for file in Path(REPO).rglob('*'):
        if not file.is_file():
            continue
        with file.open() as keyfile:
            key = keyfile.readline().strip()
            if not WG_PUBKEY_PATTERN.match(key):
                print(f"Warning: Skipping {file.name}. Key is invalid!")
                continue
            repokeys[key].append(file)
    return repokeys

with lock():
    pull_repo()

    keys = read_repo_keys(REPO)
    duplicates = {key: files for key, files in keys.items() if len(files) > 1}

    for key, dups in duplicates.items():
        dups.sort(key=lambda x: x.stat().st_ctime)
        latest_key = dups[-1]
        for old in dups[:-1]:
            old.unlink()
            commit_repo(old.name)
    push_repo()

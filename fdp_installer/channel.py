"""Read the ga-fdp channel with the standard library only."""

import json
import re
import urllib.request

REPODATA_URL = "https://conda.anaconda.org/ga-fdp/noarch/repodata.json"
_RELEASE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def _fetch(url: str) -> str:
    # A User-Agent is set on purpose: federation hosts 403 urllib's default.
    req = urllib.request.Request(url, headers={"User-Agent": "fdp-installer"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def latest_core_version(fetch=_fetch) -> str:
    """Newest release (x.y.z, no pre-release suffix) of fdp-core on the channel.

    Both repodata keys are read: `packages` holds legacy .tar.bz2 files and
    `packages.conda` the current ones; reading one alone reports stale
    versions. Comparison is on integer tuples, never on strings.
    """
    try:
        repodata = json.loads(fetch(REPODATA_URL))
    except (OSError, ValueError) as e:
        raise RuntimeError(
            f"could not read {REPODATA_URL}: {e}\n"
            "Pass --core-version <x.y.z> to skip the channel lookup.") from e
    best = None
    for key in ("packages", "packages.conda"):
        for meta in repodata.get(key, {}).values():
            if meta.get("name") != "fdp-core":
                continue
            m = _RELEASE.fullmatch(meta.get("version", ""))
            if not m:
                continue
            tup = tuple(int(x) for x in m.groups())
            if best is None or tup > best[0]:
                best = (tup, meta["version"])
    if best is None:
        raise RuntimeError("no fdp-core release found on the ga-fdp channel")
    return best[1]

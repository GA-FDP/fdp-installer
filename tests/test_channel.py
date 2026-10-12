import json

from fdp_installer.channel import latest_core_version, REPODATA_URL


def _repodata(versions):
    return json.dumps({
        "packages": {f"fdp-core-{v}-h0.tar.bz2": {"name": "fdp-core", "version": v}
                     for v in versions[:1]},
        "packages.conda": {f"fdp-core-{v}-h0.conda": {"name": "fdp-core", "version": v}
                           for v in versions[1:]},
        "x": {"other-1.0-h0.conda": {"name": "other", "version": "9.9"}},
    })


def test_picks_newest_by_numeric_order():
    fetch = lambda url: _repodata(["1.1.9", "1.1.13", "1.2.0", "1.10.0"])
    assert latest_core_version(fetch) == "1.10.0"


def test_skips_prereleases():
    fetch = lambda url: _repodata(["1.28.0", "1.29.0rc1"])
    assert latest_core_version(fetch) == "1.28.0"


def test_reads_both_repodata_keys():
    fetch = lambda url: _repodata(["1.3.0", "1.2.0"])
    assert latest_core_version(fetch) == "1.3.0"


def test_fetches_the_noarch_repodata():
    seen = []
    def fetch(url):
        seen.append(url)
        return _repodata(["1.0.0"])
    latest_core_version(fetch)
    assert seen == [REPODATA_URL]


def test_no_fdp_core_raises():
    import pytest
    fetch = lambda url: json.dumps({"packages": {}, "packages.conda": {}})
    with pytest.raises(RuntimeError):
        latest_core_version(fetch)


def test_fetch_failure_becomes_runtime_error_with_hint():
    import pytest
    def fetch(url):
        raise OSError("no network")
    with pytest.raises(RuntimeError, match="--core-version"):
        latest_core_version(fetch)

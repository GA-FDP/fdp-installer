"""Prove the image reaches real data over Pelican. Run as:

    fdp run python live_check.py

inside the container with BEARER_TOKEN set (CI) or after `fdp login` (a Mac).
"""
import numpy as np

from toksearch import MdsSignal
from toksearch_d3d import PtDataSignal

SHOT = 198873

ip = PtDataSignal("ip").fetch(SHOT)
assert ip["data"].size > 1000, ip["data"].shape
assert np.nanmax(np.abs(ip["data"])) > 1e5, "ip is not in amps or is empty"
print(f"ptdata ip: {ip['data'].size} samples, peak {np.nanmax(np.abs(ip['data']))/1e6:.2f} MA")

ipmhd = MdsSignal(r"\ipmhd", "efit01").fetch(SHOT)
assert ipmhd["data"].size > 10, ipmhd["data"].shape
print(f"efit01 ipmhd: {ipmhd['data'].size} samples")
print("OK: live check passed")

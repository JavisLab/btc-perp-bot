"""Full deterministic ETH performance replay with socket operations blocked."""
import argparse
import gzip
import hashlib
import json
import socket
import ssl
from pathlib import Path

import eth_transfer_study as study
import verify_eth_transfer_study as verify
import audit_eth_transfer_exposure as exposure


def denied(*args,**kw):
    raise RuntimeError('Network disabled for ETH offline reproduction')


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    socket.socket.connect=denied;socket.socket.connect_ex=denied;socket.socket.sendto=denied
    socket.create_connection=denied;socket.getaddrinfo=denied
    try:socket.create_connection(('example.invalid',443))
    except RuntimeError:pass
    else:raise AssertionError('Network denial probe failed')
    for period in ('main','recent'):study.run(a.out,period)
    verify.RUN=a.out;verify.run();exposure.run(a.out)
    expected=sorted(p for p in a.source.iterdir() if p.name!='reproduction.json' and p.is_file())
    actual=sorted(p for p in a.out.iterdir() if p.name!='reproduction.json' and p.is_file())
    assert [p.name for p in expected]==[p.name for p in actual]
    comparisons=[]
    for p in expected:
        other=a.out/p.name
        assert p.read_bytes()==other.read_bytes(),p.name
        comparisons.append({'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size})
    evidence={'network':'socket connect/connect_ex/sendto/create_connection/getaddrinfo denied; denial probe passed',
        'matched_files':len(comparisons),'files':comparisons,'all_bytes_equal':True,
        'source_hashes':{p:hashlib.sha256((study.ROOT/p).read_bytes()).hexdigest() for p in [
            'tools/eth_transfer_study.py','tools/verify_eth_transfer_study.py','tools/audit_eth_transfer_exposure.py','tools/structural_study.py','tools/price_volume_study.py']}}
    study.write_fixed(a.source/'reproduction.json',study.canonical(evidence))
    print(json.dumps({'matched_files':len(comparisons),'all_bytes_equal':True}),flush=True)


if __name__=='__main__':main()

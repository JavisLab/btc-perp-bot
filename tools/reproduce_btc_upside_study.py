"""Socket-blocked full reproduction of ONLY the new BTC upside-variance experiment."""
import argparse,json,socket,ssl
from pathlib import Path
import btc_upside_study as study
import verify_btc_upside_study as verify

def deny(*args,**kwargs):raise RuntimeError('Network disabled for BTC research replay')
def run(source,out):
 for k in ('connect','connect_ex','sendto'):setattr(socket.socket,k,deny)
 socket.create_connection=socket.getaddrinfo=deny
 try:socket.create_connection(('invalid.example',443))
 except RuntimeError:pass
 else:raise AssertionError('Network block failed')
 study.run(out);verify.run(out)
 files=sorted(p for p in source.iterdir() if p.is_file() and not p.name.startswith('reproduction'))
 actual=sorted(p for p in out.iterdir() if p.is_file() and not p.name.startswith('reproduction'))
 assert [p.name for p in files]==[p.name for p in actual]
 hashes={}
 for p in files:
  assert p.read_bytes()==(out/p.name).read_bytes(),p.name
  hashes[p.name]=study.sha(p.read_bytes())
 study.write(source/'reproduction.json',{'network':'connect/connect_ex/sendto/create_connection/getaddrinfo blocked; denial probe passed','matched_files':len(files),'all_bytes_equal':True,'sha256':hashes})
 print(json.dumps({'matched_files':len(files),'all_bytes_equal':True}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.source,a.out)

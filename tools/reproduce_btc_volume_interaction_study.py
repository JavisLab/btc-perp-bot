"""Socket-blocked reproduction of only the new flow experiment."""
import argparse,json,socket,ssl
from pathlib import Path
import btc_volume_interaction_study as study
import verify_btc_volume_interaction_study as verify

def deny(*args,**kwargs):raise RuntimeError('Network disabled for BTC flow replay')
def run(source,out):
 for k in ('connect','connect_ex','sendto'):setattr(socket.socket,k,deny)
 socket.create_connection=socket.getaddrinfo=deny
 try:socket.create_connection(('invalid.example',443))
 except RuntimeError:pass
 else:raise AssertionError('Network block failed')
 study.run(out);verify.run(out)
 a=sorted(p.name for p in source.iterdir() if p.is_file() and p.name!='reproduction.json');b=sorted(p.name for p in out.iterdir() if p.is_file() and p.name!='reproduction.json');assert a==b
 hashes={}
 for name in a:
  x=(source/name).read_bytes();assert x==(out/name).read_bytes(),name;hashes[name]=study.sha(x)
 study.write(source/'reproduction.json',{'network':'socket connect/connect_ex/sendto/create_connection/getaddrinfo denied, probe passed','matched_files':len(a),'all_bytes_equal':True,'sha256':hashes});print(json.dumps({'matched_files':len(a),'all_bytes_equal':True}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.source,a.out)

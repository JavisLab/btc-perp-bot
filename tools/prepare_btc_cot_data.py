"""Normalize only BTC CFTC positions and conservative, outage-aware publication clocks."""
import json,re,datetime as dt
from pathlib import Path
from btc_perp_bot.research.archive import DAY,ms,sha,canonical
ROOT=Path(__file__).resolve().parents[1];P=ROOT/'data/btc-cot-20261002'
def textfile(name):
 x=json.loads((P/name).read_text())
 while isinstance(x,str):x=json.loads(x)
 if 'value' in x:x=json.loads(x['value'])
 return x['text']
def release_overrides():
 old=textfile('history-official.json');matches=list(re.finditer(r'([A-Z][a-z]+ \d{1,2}, 2023):',old));out={}
 for i,m in enumerate(matches):
  block=old[m.end():matches[i+1].start() if i+1<len(matches) else len(old)]
  if 'Today, staff is issuing' not in block:continue
  found=re.search(r'originally scheduled to be published on ([A-Z][a-z]+ \d{1,2}, 2023)',block)
  if found:
   release=dt.datetime.strptime(m[1],'%B %d, %Y').date();due=dt.datetime.strptime(found[1],'%B %d, %Y').date();out[(due-dt.timedelta(days=3)).isoformat()]=release.isoformat()
 assert len(out)==7
 current=textfile('accelerated2025-source.json');triples=re.findall(r'(\d\d/\d\d/\d{4})\s*(\d\d/\d\d/\d{4})\s*(\d\d/\d\d/\d{4})',current);assert len(triples)==13
 for reported,_,release in triples:out[dt.datetime.strptime(reported,'%m/%d/%Y').date().isoformat()]=dt.datetime.strptime(release,'%m/%d/%Y').date().isoformat()
 assert 'January 13, 2025' in old;out['2025-01-07']='2025-01-13';return out

def run():
 raw=(P/'btc-futures-only.json').read_bytes();assert sha(raw)=='707932e8df4ebd9d2035591a5c9b017b485f71d98d7aaefdba0aeb5349b6b34b';source=json.loads(raw);over=release_overrides();rows=[]
 for r in source:
  date=r['report_date_as_yyyy_mm_dd'][:10];t=ms(date);pub=over.get(date);available=max(t+10*DAY,ms(pub)+2*DAY if pub else 0)
  rows.append({'report_date':date,'report_time':t,'source':available,'expiry':t+21*DAY,'public_date_override':pub,'long':int(r['lev_money_positions_long']),'short':int(r['lev_money_positions_short']),'spread':int(r['lev_money_positions_spread']),'oi':int(r['open_interest_all']),'contract':'133741','unit_btc':5})
 assert all(a['source']<=b['source'] for a,b in zip(rows,rows[1:]));b=canonical(rows);(P/'reports.json').write_bytes(b);proof={'rows':len(rows),'raw_sha256':sha(raw),'reports_sha256':sha(b),'special_clocks':len(over),'source_files':{n:sha((P/n).read_bytes()) for n in ['history-official.json','accelerated2025-source.json','faq-official.json','release2026-official.json']},'max_source_age_days':max((e['source']-e['report_time'])//DAY for e in rows),'already_expired_at_source':sum(e['source']>=e['expiry'] for e in rows),'timing_scope':'10day conservative ordinary assumption; 2023 issued notices / 2025 intended revised schedule +2days; not exact full historical receipt proof'};(P/'clock-audit.json').write_bytes(canonical(proof));print(json.dumps(proof),flush=True)
if __name__=='__main__':run()

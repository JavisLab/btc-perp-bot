"""Read-only independent audit of frozen BTC ETF aggregate source subsets and API overlap."""
import collections,hashlib,json,re
from pathlib import Path
from decimal import Decimal
from html.parser import HTMLParser
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data/btc-etfshort-20261002';SYMS=('IBIT','FBTC','GBTC')
def digest(raw):return hashlib.sha256(raw).hexdigest()
class Index(HTMLParser):
 def __init__(self):super().__init__();self.urls=[]
 def handle_starttag(self,tag,attributes):
  u=dict(attributes).get('href','')
  if tag=='a' and re.fullmatch(r'https://cdn\.finra\.org/equity/regsho/daily/CNMSshvol\d{8}\.txt',u):self.urls.append(u)
def run():
 dates=set();months=[];revisions=[]
 for p in sorted((DATA/'indices').glob('*.html')):
  parse=Index();raw=p.read_bytes();parse.feed(raw.decode());assert parse.urls,p
  months.append(p.stem)
  for u in parse.urls:
   date=re.search(r'(\d{8})\.txt$',u).group(1)
   if '20240111'<=date<='20260831':dates.add(date)
 expected_months=[f'{y}-{m:02d}' for y in (2024,2025,2026) for m in range(1,13) if (y,m)<=(2026,8)]
 bydate={};complete=[];missing=[];decimal_fields=0
 for date in sorted(dates):
  p=DATA/'raw'/f'CNMSshvol{date}.txt';meta=Path(str(p)+'.meta.json')
  if not p.exists() or not meta.exists():missing.append(date);continue
  m=json.loads(meta.read_text());raw=p.read_bytes();assert digest(raw)==m['subset_sha256'] and m['date']==date and m['filename']==p.name and m['source_trailer_records']>=m['retained_rows'];assert re.fullmatch('[0-9a-f]{64}',m['full_response_sha256']);lines=raw.decode().splitlines();assert lines[0].split('|')==['Date','Symbol','ShortVolume','ShortExemptVolume','TotalVolume','Market'];items={}
  for line in lines[1:]:
   d,n,q,e,v,venue=line.split('|');assert d==date and n in SYMS and n not in items
   qd,ed,vd=Decimal(q),Decimal(e),Decimal(v);assert 0<=ed<=qd<=vd and vd>0
   assert set(venue.split(','))<=set('BQND');decimal_fields+=sum('.' in z for z in (q,e,v));items[n]={'short':q,'exempt':e,'total':v,'markets':venue}
  assert sorted(items)==sorted(m['retained_symbols']) and len(items)==m['retained_rows'];bydate[date]=items;complete.append(date)
 api_audit={};matches=0;differences=[];api_dates=set()
 log=json.loads((DATA/'api-fetch-log.json').read_text())
 for n in SYMS:
  p=DATA/(n+'-api-raw.json');raw=p.read_bytes();a=json.loads(raw,parse_float=Decimal);receipt=next(e for e in log if e['symbol']==n);assert len(a)==receipt['records']==int(receipt['response_headers']['record-total']) and digest(raw)==receipt['response_sha256'];groups=collections.defaultdict(list);keys=set()
  for x in a:
   assert x['securitiesInformationProcessorSymbolIdentifier']==n;k=(x['tradeReportDate'],x['marketCode']);assert k not in keys,(n,k);keys.add(k);groups[k[0]].append(x);assert 0<=Decimal(x['shortExemptParQuantity'])<=Decimal(x['shortParQuantity'])<=Decimal(x['totalParQuantity'])
  api_audit[n]={'records':len(a),'dates':len(groups),'start':min(groups),'end':max(groups),'full_requested_period':min(groups)<='2024-01-11'}
  for ds,g in groups.items():
   date=ds.replace('-','');api_dates.add(date)
   if date not in bydate or n not in bydate[date]:continue
   b=bydate[date][n];vals={k:sum(Decimal(x[f]) for x in g) for k,f in [('short','shortParQuantity'),('exempt','shortExemptParQuantity'),('total','totalParQuantity')]}
   if any(vals[k]!=Decimal(b[k]) for k in vals) or set(b['markets'].split(','))!={x['marketCode'] for x in g}:differences.append({'date':date,'symbol':n,'cdn':b,'api':{k:str(v) for k,v in vals.items()}})
   else:matches+=1
 gaps=[{'date':d,'present':sorted(a)} for d,a in sorted(bydate.items()) if set(a)!=set(SYMS)]
 report={'scope':'source audit only; no BTC price/return joined, no strategy performance calculated','index_months':months,'missing_index_months':sorted(set(expected_months)-set(months)),'indexed_days':len(dates),'downloaded_days':len(complete),'missing_indexed_files':missing,'missing_symbols':gaps,'raw_decimal_fields':decimal_fields,'api_retention':api_audit,'api_cdn_exact_symbol_days':matches,'api_cdn_differences':differences,'api_dates_missing_in_index':sorted(api_dates-dates),'first_day':min(complete) if complete else None,'last_day':max(complete) if complete else None,'all_indexed_data_complete':not missing and set(months)==set(expected_months) and not gaps,'vintage_limit':'current public archives; first-published versions/revisions not fully reconstructed; site rate limits respected; daily regular-hours marked-short volume not holdings; ShortVolume already includes exemptions'}
 (DATA/'data-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False),flush=True)
 if report['all_indexed_data_complete'] and not differences:
  payload={'symbols':list(SYMS),'rows':[dict(date=d,values=x) for d,x in sorted(bydate.items())],'scope':report['vintage_limit']};raw=json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode();(DATA/'btc-etfshort.json').write_bytes(raw);print('FROZEN_DATA_SHA256',digest(raw),flush=True)
if __name__=='__main__':run()

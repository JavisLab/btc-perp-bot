"""Independent Decimal audit of public daily CSVs/vintages/normalization, not full-node reconstruction."""
import csv,datetime as dt,hashlib,io,json,math,tarfile
from decimal import Decimal as D
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'data/btc-dormancy-20261003';WEB=ROOT/'data/btc-web-20261003';DAY=86400000

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stamp(s):return int(dt.datetime.strptime(s,'%Y-%m-%d').replace(tzinfo=dt.timezone.utc).timestamp()*1000)
def audit(save=True):
 manifest=json.loads((BASE/'archive-manifest.json').read_text());norm=json.loads((BASE/'daily.json').read_text());assert digest(BASE/'daily.json')==manifest['normalized_sha256'];series={};raw_rows=0
 for key,m in manifest['series'].items():
  p=ROOT/m['path'];assert digest(p)==m['sha256'];rows=list(csv.DictReader(p.open()));data={}
  for x in rows:
   t=stamp(x['date']);assert t not in data and x['unit']==m['unit'] and x['series_id']==p.stem and x['frequency']=='daily';data[t]=D(x['value'])
  assert sorted(data)==list(range(min(data),max(data)+DAY,DAY));assert len(rows)==m['rows'];series[key]=data;raw_rows+=len(rows)
 ap=ROOT/manifest['archive']['path'];assert digest(ap)==manifest['archive']['sha256'] and hashlib.md5(ap.read_bytes()).hexdigest()==manifest['archive']['md5'];overlaps={}
 with tarfile.open(ap,'r:gz') as tar:
  for key,m in manifest['series'].items():
   fn=Path(m['path']).name;members=[x for x in tar.getmembers() if x.isfile() and x.name.endswith('/'+fn)];assert len(members)==1;old=list(csv.DictReader(io.StringIO(tar.extractfile(members[0]).read().decode())));count=0
   for row in old:
    t=stamp(row['date']);a,b=D(row['value']),series[key][t];assert a==b or a.is_nan() and b.is_nan();count+=1
   overlaps[key]=count
 txm=manifest['independent_transaction_counts'];assert digest(ROOT/txm['path'])==txm['sha256'];tx={}
 for x in json.loads((ROOT/txm['path']).read_text())['values']:
  t=int(x['x'])*1000;v=D(str(x['y']));assert t%DAY==0 and t not in tx and v>=0 and v==v.to_integral();tx[t]=v
 assert [r['day'] for r in norm['days']]==list(range(stamp('2020-01-01'),stamp('2026-09-01'),DAY));errors=[];invalid=[];deltas={}
 for r in norm['days']:
  t=r['day'];why=[]
  assert r['date']==dt.datetime.fromtimestamp(t/1000,dt.timezone.utc).strftime('%Y-%m-%d') and r['base_assumed_available']==t+6*DAY
  for key,values in series.items():assert (None if r[key] is None else D(r[key]))==values.get(t)
  assert (None if r['independent_transaction_count'] is None else D(r['independent_transaction_count']))==tx.get(t)
  vals={key:values.get(t) for key,values in series.items()}
  if any(v is None for v in vals.values()):why.append('missing_obm')
  elif not all(v.is_finite() and v>=0 for v in vals.values()):why.append('nonfinite_or_negative')
  elif not all(vals[k]>0 for k in ('spent','blocks','transactions')):why.append('zero_denominator_or_activity')
  elif any(vals[k]!=vals[k].to_integral() for k in ('blocks','transactions')):why.append('noninteger_count')
  else:
   err=abs(vals['cdd']/vals['spent']-vals['dormancy']);errors.append(err)
   if err>D('2e-12') or not D(0)<=vals['dormancy']<=D(t-stamp('2009-01-03'))/DAY+1:why.append('age_ratio_or_bound')
  if t not in tx:why.append('independent_count_missing')
  elif vals['transactions']!=tx[t]:why.append('independent_count_mismatch');deltas[t]=vals['transactions']-tx[t]
  assert why==r['invalid_reasons'] and r['valid']==(not why)
  if why:invalid.append({'date':r['date'],'reasons':why})
 assert invalid==manifest['invalid_days'] and len(norm['days'])-len(invalid)==manifest['valid_days']
 pairs=[];dd=sorted(deltas)
 for a,b in zip(dd[::2],dd[1::2]):assert b-a==DAY and deltas[a]+deltas[b]==0;pairs.append([a,b])
 assert len(pairs)*2==len(dd)
 histories=json.loads((WEB/'q118-dormancy-history.json').read_text());clock=[]
 for i,h in enumerate(histories):
  p=ROOT/manifest['series']['dormancy']['path'] if i==0 else WEB/f"q118-dormancy-{h['sha'][:8]}.csv";rr=list(csv.DictReader(p.open()));last=dt.date.fromisoformat(rr[-1]['date']);commit=dt.datetime.fromisoformat(h['commit']['committer']['date'].replace('Z','+00:00'));assert (commit.date()-last).days==5;clock.append({'commit':h['sha'],'commit_time':commit.isoformat(),'last_day':str(last),'sha256':digest(p),'lag_calendar_days':5})
 report={'raw_csv_rows':raw_rows,'current_series':5,'archive_series_equal_rows':overlaps,'normalized_days':len(norm['days']),'valid_days':manifest['valid_days'],'invalid_days':invalid,'independent_count_adjacent_pairs':pairs,'maximum_decimal_ratio_error':str(max(errors)),'clock_probes':clock,'normalized_sha256':digest(BASE/'daily.json'),'scope':'Independently re-parsed public daily aggregate sources and archived versions; no independent full-node or individual UTXO/transaction reconstruction. Publication lag based on limited 2026 snapshots, pre-July2026 retrospective reconstruction only.'}
 if save:(BASE/'independent-audit.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
 return series,tx,report
if __name__=='__main__':print(json.dumps(audit()[2],indent=2))

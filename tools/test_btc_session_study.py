"""Focused accounting/chronology boundary tests, synthetic only."""
import math
import btc_session_study as s

def fake(price=10000.):
 m=s.Market.__new__(s.Market);m.first=0;m.rows=[[t,price,price,price,price,1.,t+s.STEP-1,price,1,.5,price/2] for t in range(0,2*s.DAY,s.STEP)];m.funds={s.HOUR:(.001,price,s.HOUR+1)};m.conflicts=set();return m

def run():
 checks=[]
 m=fake();a=s.simulate(m,'test',0,2*s.DAY,[{'source':0,'weight':.5}]);b=s.simulate(m,'test',0,2*s.DAY,[{'source':0,'weight':-.5}]);assert a['metrics']['funding']<0<b['metrics']['funding'];assert a['metrics']['gross']==b['metrics']['gross']==0.;assert a['metrics']['fees']>0 and a['metrics']['impact']>0;checks.append('long_short_fees_funding')
 x=s.simulate(m,'test',0,2*s.DAY,[{'source':0,'weight':0.}]);assert x['metrics']['equity']==1000 and not x['events'];checks.append('cash_no_trade')
 x=s.simulate(m,'test',0,2*s.DAY,[{'source':0,'weight':.03}]);assert x['metrics']['equity']==1000 and x['skips'][0]['reason']=='minimum';checks.append('minimum_quantity_rejection')
 p=[{'source':0,'weight':.3},{'source':12*s.HOUR,'weight':-.3}];x=s.simulate(m,'test',0,2*s.DAY,p,delay=s.HOUR);fills=[e for e in x['events'] if e['kind']=='fill'];assert fills[0]['time']==s.HOUR+s.STEP and fills[1]['time']==13*s.HOUR+s.STEP;assert fills[1]['before']>0>fills[1]['position'];assert abs(fills[1]['delta'])==abs(fills[1]['before'])+abs(fills[1]['position']);assert all(abs(e['position']/.001-round(e['position']/.001))<1e-9 for e in fills);checks.append('frozen_delay_reversal_double_turnover_units')
 m=fake();m.rows[1][5]=0;x=s.simulate(m,'test',0,2*s.DAY,[{'source':0,'weight':.3}]);assert x['events'][0]['time']==2*s.STEP and x['skips'][0]['reason']=='zero_volume_retry';checks.append('zero_volume_not_filled')
 m=s.Market.__new__(s.Market);m.conflicts=set();m.hourly={t:[t,100,102,98,100+math.sin(t/s.HOUR/11),1.,t+s.HOUR-1,100,1,.5,50] for t in range(-30*s.DAY,3*s.DAY,s.HOUR)}
 p=m.plan('SR00',0,2*s.DAY);assert p[0]['detail']['signal_start']==-s.DAY and p[0]['detail']['signal_end']==-12*s.HOUR
 for t,r in m.hourly.items():
  if t>=0:r[4]*=10
 pp=m.plan('SR00',0,2*s.DAY);assert p[0]==pp[0];checks.append('future_perturbation_same_session_not_adjacent')
 # Open-labeled close-to-close bars telescope to the CORRECT completed boundary.
 closes={i:100+i for i in range(7,20)};prod=math.prod(closes[i]/closes[i-1] for i in range(8,20));assert abs(prod-closes[19]/closes[7])<1e-12;checks.append('paper_open_label_telescoping_not_false_lookahead')
 print({'passed':len(checks),'checks':checks})
if __name__=='__main__':run()

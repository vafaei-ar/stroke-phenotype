#!/usr/bin/env python3
"""Local-only Center 1 first-event selection sensitivity analysis.

Never commit or upload record-level input files or row-level output.
The script uses the protected legacy feature table before patient first-event
selection and the frozen historical monthly counts. It stops unless its
baseline exactly reproduces D0-D8 on the requested 85-month study window.

Outputs contain monthly aggregate counts and summary metrics only.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import numpy as np
import pandas as pd

FEATURE_COLUMNS = ['PATID','ENCOUNTERID','FACILITYID','ADMIT_DATE',
                   'MRI-2','MRI-ENC','CT-2','CT-ENC','lip','phy']
DEFS=[f'D{i}' for i in range(9)]

def bool_flag(series):
    normalized=series.astype('string').str.strip().str.lower()
    valid_true={'true','t','yes','y','1'}
    valid_false={'false','f','no','n','0','nan','none','<na>',''}
    if set(normalized.dropna())-(valid_true|valid_false):
        raise ValueError('Unexpected boolean code in flag column')
    return normalized.isin(valid_true)

def read_details(path):
    d=pd.read_csv(path,dtype={'PATID':'string','ENCOUNTERID':'string','FACILITYID':'string'},low_memory=False)
    miss=set(FEATURE_COLUMNS)-set(d)
    if miss:raise ValueError(f'Missing original detail fields: {sorted(miss)}')
    d['ADMIT_DATE']=pd.to_datetime(d['ADMIT_DATE'],errors='raise')
    for col in FEATURE_COLUMNS[4:]:d[col]=bool_flag(d[col])
    d['mri']=d['MRI-2']|d['MRI-ENC']
    d['ct']=d['CT-2']|d['CT-ENC']
    d['lipid']=d['lip'];d['rehab']=d['phy']
    return d

def read_monthly(path,study_start,study_end):
    d=pd.read_csv(path)
    for key in ['month','Month','MONTH','date','Date','Unnamed: 0']:
        if key in d.columns:
            d=d.rename(columns={key:'month'});break
    if 'month' not in d.columns:d=d.rename(columns={d.columns[0]:'month'})
    if 'SR' not in d.columns:raise ValueError('Baseline aggregate file requires SR column')
    miss=set(DEFS)-set(d)
    if miss:raise ValueError(f'Frozen aggregate file lacks D0-D8 columns: {sorted(miss)}')
    d['month']=pd.to_datetime(d['month'],errors='raise').dt.to_period('M').dt.to_timestamp()
    d=d.set_index('month').sort_index()
    months=pd.date_range(pd.Timestamp(study_start),pd.Timestamp(study_end),freq='MS')
    if len(d)!=len(months) or not d.index.equals(months):
        raise ValueError('Baseline registry months do not exactly match the study window')
    if d[['SR']+DEFS].isna().any().any():raise ValueError('Missing monthly counts')
    return d

def read_primary_map(path):
    m=pd.read_csv(path,dtype={'PATID':'string','ENCOUNTERID':'string'},low_memory=False)
    required=['PATID','ENCOUNTERID','primary_ischemic_dx']
    if any(x not in m for x in required):
        raise ValueError('Primary-map file needs PATID, ENCOUNTERID, primary_ischemic_dx')
    if m.duplicated(['PATID','ENCOUNTERID']).any():
        raise ValueError('Primary-map file must have one row per patient/encounter')
    if m['primary_ischemic_dx'].isna().any():
        raise ValueError('Primary-map has missing diagnosis-position values; code negative encounters as 0 explicitly')
    m['primary_ischemic_dx']=bool_flag(m['primary_ischemic_dx'])
    return m[required]

def read_registry_events(path,datecol='StrokeDate'):
    r=pd.read_csv(path,dtype={'MRN':'string'},low_memory=False)
    req=['MRN','Type','Diagnosis',datecol]
    if any(x not in r for x in req):raise ValueError(f'Registry rows require {req}')
    r=r[(r['Type'].astype(str).str.strip().str.casefold()=='ischemic') &
        (r['Diagnosis'].astype(str).str.strip().str.casefold()=='primary')].copy()
    r['event_date']=pd.to_datetime(r[datecol],errors='raise')
    return r

def first_events(d,facility,facility_first=False,primary_only=False,lookback=None):
    a=d.copy()
    if lookback is not None:
        a=a[a['ADMIT_DATE']>=pd.Timestamp(lookback)].copy()
    if primary_only:
        if 'primary_ischemic_dx' not in a:raise ValueError('Primary diagnostic status unavailable')
        if a['primary_ischemic_dx'].isna().any():raise ValueError('Primary diagnostic map incomplete')
        a=a[a['primary_ischemic_dx']].copy()
    mask=a['FACILITYID'].str.contains(facility,case=False,regex=False,na=False)
    if facility_first:a=a.loc[mask].copy()
    # Preserve the legacy notebook's quicksort and first-encounter tie behavior.
    a=a.sort_values('ADMIT_DATE',kind='quicksort')
    a=a.drop_duplicates('PATID',keep='first')
    if not facility_first:
        a=a[a['FACILITYID'].str.contains(facility,case=False,regex=False,na=False)].copy()
    return a

def monthly_counts(selected, months):
    a=selected.copy()
    a['month']=a['ADMIT_DATE'].dt.to_period('M').dt.to_timestamp()
    a['D0']=True
    a['D1']=(a['ct']|a['mri'])&a['lipid']
    a['D2']=(a['ct']|a['mri'])&(a['lipid']|a['rehab'])
    a['D3']=a['mri']&a['lipid']
    a['D4']=a['mri']&(a['lipid']|a['rehab'])
    a['D5']=a['ct']|a['mri']
    a['D6']=a['mri']&a['lipid']&a['rehab']
    a['D7']=a['mri']
    a['D8']=a['ct']&a['lipid']
    out=pd.DataFrame(index=months)
    for definition in DEFS:
        s=a.loc[a[definition]].groupby('month').size()
        out[definition]=s.reindex(months,fill_value=0).astype(int)
    return out

def monthly_registry_lookback(r,lookback,months):
    a=r[r['event_date']>=pd.Timestamp(lookback)].copy()
    a=a.sort_values('event_date',kind='quicksort').drop_duplicates('MRN',keep='first')
    m=a['event_date'].dt.to_period('M').dt.to_timestamp()
    return m.value_counts().reindex(months,fill_value=0).astype(int)

def summarize(counts,registry,scenario):
    rows=[]
    for d in DEFS:
        y=counts[d].to_numpy(dtype=float);r=registry.to_numpy(dtype=float)
        e=y-r
        mae=np.mean(np.abs(e));nmae=(mae/np.mean(r)*100) if np.mean(r)>0 else float('nan')
        corr=np.corrcoef(y,r)[0,1] if np.std(y)>0 and np.std(r)>0 else float('nan')
        rows.append({'scenario':scenario,'definition':d,'monthly_MAE':mae,'nMAE_pct':nmae,
                     'mean_signed_error':np.mean(e),'total_EHR':int(y.sum()),
                     'total_registry':int(r.sum()),'pearson_r':corr})
    t=pd.DataFrame(rows)
    t['MAE_rank']=t['monthly_MAE'].rank(method='min',ascending=True).astype(int)
    return t

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--legacy-details',required=True,help='Protected pre-dedup df_phen_details.csv')
    p.add_argument('--historical-monthly',required=True,help='Frozen PS_conditions.csv containing SR, D0-D8')
    p.add_argument('--facility-contains',required=True,help='Local site substring, never disclose')
    p.add_argument('--out-dir',required=True,help='Local secure directory for aggregate output')
    p.add_argument('--primary-map',help='Protected encounter-level mapping for primary ischemic diagnosis')
    p.add_argument('--registry-events',help='Protected registry rows with MRN, Type, Diagnosis, and date')
    p.add_argument('--registry-date-column',default='StrokeDate')
    p.add_argument('--lookback-start',help='Shared source-coverage start, YYYY-MM-DD; requires registry events')
    p.add_argument('--study-start',default='2016-12-01')
    p.add_argument('--study-end',default='2023-12-01')
    args=p.parse_args()
    if args.lookback_start and not args.registry_events:
        p.error('--lookback-start requires --registry-events; aggregate SR cannot establish a matched source lookback')
    if args.lookback_start and pd.Timestamp(args.lookback_start) > pd.Timestamp(args.study_start):
        p.error('--lookback-start must be on or before --study-start for a full-window comparison')
    if not args.facility_contains.strip():
        p.error('--facility-contains cannot be blank')
    d=read_details(args.legacy_details)
    frozen=read_monthly(args.historical_monthly,args.study_start,args.study_end)
    if args.primary_map:
        m=read_primary_map(args.primary_map)
        d=d.merge(m,on=['PATID','ENCOUNTERID'],how='left',validate='many_to_one')
        if d['primary_ischemic_dx'].isna().any():
            raise ValueError('Incomplete encounter-level primary diagnosis mapping')
    months=frozen.index
    # Manuscript regression checkpoint. The synthetic test window below bypasses this check.
    if months[0] == pd.Timestamp('2016-12-01') and months[-1] == pd.Timestamp('2023-12-01') and len(months) == 85:
        expected={'SR':4000,'D0':6582,'D1':4953,'D2':5872,'D3':4320,'D4':4821,
                  'D5':6192,'D6':3388,'D7':5016,'D8':4189}
        wrong={key:(int(frozen[key].sum()),val) for key,val in expected.items()
               if int(frozen[key].sum()) != val}
        if wrong:
            raise RuntimeError(f'Frozen Center 1 totals disagree with manuscript: {wrong}. Stop.')
    scenarios={'baseline':{'facility_first':False,'primary_only':False,'lookback':None},
               'facility_filter_first':{'facility_first':True,'primary_only':False,'lookback':None}}
    if args.primary_map:
        scenarios['primary_diagnosis_only']={'facility_first':False,'primary_only':True,'lookback':None}
        scenarios['facility_first_and_primary']={'facility_first':True,'primary_only':True,'lookback':None}
    if args.lookback_start:
        scenarios['aligned_observed_lookback']={'facility_first':False,'primary_only':False,'lookback':args.lookback_start}
        scenarios['aligned_lookback_and_facility_first']={'facility_first':True,'primary_only':False,'lookback':args.lookback_start}
    registry_events=read_registry_events(args.registry_events,args.registry_date_column) if args.registry_events else None
    agg=[];summary=[]
    for name,kwargs in scenarios.items():
        selected=first_events(d,args.facility_contains,**kwargs)
        ct=monthly_counts(selected,months)
        if name=='baseline':
            diff=ct[DEFS].astype(int).subtract(frozen[DEFS].astype(int))
            bad=diff.abs().max().max()
            if bad:
                raise RuntimeError(f'Frozen Center 1 baseline NOT reproduced. Max monthly difference={bad}. Stop; inspect inputs before interpreting sensitivities.')
        reference=(monthly_registry_lookback(registry_events,kwargs['lookback'],months)
                   if kwargs['lookback'] else frozen['SR'].astype(int))
        temp=ct.copy();temp['SR']=reference
        temp.insert(0,'month',months.strftime('%Y-%m'))
        temp.insert(0,'scenario',name)
        agg.append(temp)
        summary.append(summarize(ct,reference,name))
    allsummary=pd.concat(summary,ignore_index=True)
    orig=allsummary[allsummary['scenario']=='baseline'].set_index('definition')
    allsummary['delta_nMAE_pp_vs_baseline']=allsummary.apply(
        lambda row:row['nMAE_pct']-orig.loc[row['definition'],'nMAE_pct'],axis=1)
    root=Path(args.out_dir);root.mkdir(parents=True,exist_ok=True)
    allsummary.to_csv(root/'center1_sensitivity_summary.csv',index=False)
    pd.concat(agg,ignore_index=True).to_csv(root/'center1_sensitivity_monthly.csv',index=False)
    print('Historical monthly D0-D8 reproduction: EXACT MATCH')
    print('Sensitivity scenarios:',', '.join(scenarios))
    print('Aggregate-only output:',str(root))
    print('Do not export the protected input tables.')

if __name__=='__main__':main()

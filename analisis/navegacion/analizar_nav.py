import csv,re,statistics as st,random,sys,json,glob
D=sys.argv[1]
def load(c):
    rows=list(csv.DictReader(open(f'{D}/nav_so101_{c}.csv',encoding='utf-8')))
    seen={};[seen.setdefault(r['run'],r) for r in rows]; return list(seen.values())
def warn(c):
    t=open(f'{D}/nav_so101_{c}.txt',encoding='utf-8').read()
    return sum(int(x) for x in re.findall(r"missed rate': (\d+)",t)), len(re.findall('nav2_activo=0',t))
R={}
for c in ['mppi','dwb','rpp']:
    rs=load(c); ok=[r for r in rs if r['success']=='True']
    f=lambda k,s=ok:[float(r[k]) for r in s]
    ms=lambda v:(round(st.mean(v),3),round(st.stdev(v),3) if len(v)>1 else 0)
    w,na=warn(c)
    R[c]=dict(n=len(rs),ok=len(ok),t=ms(f('time_sim_s')),e=ms(f('final_error_m')),L=ms(f('path_length_m')),
      dmin=ms(f('clearance_min_m',rs)),dmin_min=min(f('clearance_min_m',rs)),intr=sum(float(r['clearance_min_m'])<-0.025 for r in rs),
      col=sum(r['collision']=='True' for r in rs),rec=ms(f('recoveries',rs)),rec_n=sum(float(r['recoveries'])>0 for r in rs),
      avisos=w,sin_nav2=na,fallos=[(r['run'],r['status'],r['final_error_m']) for r in rs if r['success']!='True'],
      tiempos=f('time_sim_s'),errores=f('final_error_m'))
def perm(a,b,n=20000,s=1):
    random.seed(s);obs=abs(st.mean(a)-st.mean(b));z=a+b;k=0
    for _ in range(n):
        random.shuffle(z);k+=abs(st.mean(z[:len(a)])-st.mean(z[len(a):]))>=obs
    return round((k+1)/(n+1),4)
P={}
for a,b in [('mppi','dwb'),('mppi','rpp'),('dwb','rpp')]:
    P[a+'_'+b]=dict(t=perm(R[a]['tiempos'],R[b]['tiempos']),e=perm(R[a]['errores'],R[b]['errores']))
for c in R: R[c].pop('tiempos');R[c].pop('errores')
print(json.dumps(dict(R=R,P=P),indent=1,ensure_ascii=False))

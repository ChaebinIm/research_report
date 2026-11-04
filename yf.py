import yfinance as yf, time, json
T={'ERIC':'에릭슨','NOK':'노키아','CIEN':'시에나','CALX':'Calix','ADTN':'Adtran','GLW':'코닝','HLIT':'Harmonic','VCM.TO':'Vecima','SWKS':'Skyworks(+Qorvo)','QCOM':'퀄컴','AKAM':'아카마이','NET':'클라우드플레어','FSLY':'Fastly','STX':'씨게이트','WDC':'웨스턴디지털','AMBA':'앰바렐라','CMCSA':'컴캐스트','CHTR':'차터','EQIX':'에퀴닉스','ASTS':'AST스페이스모바일',
'032500.KQ':'케이엠더블유','088800.KQ':'에이스테크','218410.KQ':'RFHIC','050890.KQ':'쏠리드','073490.KQ':'이노와이어리스','039560.KQ':'다산네트웍스','078070.KQ':'유비쿼스홀딩스','264450.KQ':'유비쿼스','010170.KQ':'대한광통신','138080.KQ':'오이솔루션','017670.KS':'SK텔레콤','030200.KS':'KT'}
out={}
for t,n in T.items():
    for a in range(3):
        try:
            i=yf.Ticker(t).info
            out[t]=dict(name=n,price=i.get('currentPrice') or i.get('regularMarketPrice'),cur=i.get('currency'),mcap=i.get('marketCap'),fpe=i.get('forwardPE'),tpe=i.get('trailingPE'),ps=i.get('priceToSalesTrailing12Months'),evebitda=i.get('enterpriseToEbitda'),revg=i.get('revenueGrowth'),gm=i.get('grossMargins'),opm=i.get('operatingMargins'),rev=i.get('totalRevenue'),chg52=i.get('52WeekChange'),hi=i.get('fiftyTwoWeekHigh'),lo=i.get('fiftyTwoWeekLow'))
            break
        except Exception as e:
            time.sleep(3)
    time.sleep(1.2)
json.dump(out,open('yf.json','w'),ensure_ascii=False,indent=1)
for t,d in out.items():
    f=lambda x,p=1: '-' if x is None else (f'{x:.{p}f}')
    mc=d['mcap']/1e9 if d['mcap'] else None
    print(f"{t:10} {d['name']:12} {f(d['price'],2):>10} {d['cur']} mcap={f(mc)}B fPE={f(d['fpe'])} tPE={f(d['tpe'])} PS={f(d['ps'])} EV/EBITDA={f(d['evebitda'])} revG={f(d['revg'] and d['revg']*100)}% OPM={f(d['opm'] and d['opm']*100)}% 52w={f(d['chg52'] and d['chg52']*100)}%")

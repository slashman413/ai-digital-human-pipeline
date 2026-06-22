import json, urllib.request, os
from datetime import date
KEYS=[("portal","AI工具人入口"),("tokencalc","Token成本"),("pomodoro","番茄鐘"),("imageratio","出圖尺寸"),("prompts","Prompt庫"),("devtools","JSON/Regex"),("pwgen","密碼產生"),("wordcount","字數統計"),("qrgen","QR Code"),("unitconv","單位換算"),("compound","複利計算"),("llmcalc","LLM VRAM"),("etf","ETF分析"),("dna","大飆股DNA"),("global","全球大事"),("backtest","台股回測")]
def get(k):
    try:
        with urllib.request.urlopen("https://abacus.jasoncameron.dev/get/sm413-%s/views"%k,timeout=15) as r:
            return int(json.load(r).get("value",0))
    except Exception:
        return 0
cur={k:get(k) for k,_ in KEYS}
prev={}; first=True
try:
    with open("views_snapshot.json","r",encoding="utf-8") as f:
        prev=json.load(f); first=False
except Exception:
    pass
total=sum(cur.values()); tprev=sum(prev.get(k,0) for k,_ in KEYS); dtotal=total-tprev
rows=sorted(KEYS,key=lambda kn:cur[kn[0]],reverse=True)
lines=[]
for k,name in rows:
    d=cur[k]-prev.get(k,0)
    lines.append("%s：%s 次%s"%(name,format(cur[k],","),("" if first else "（+%s）"%format(d,","))))
header="📊 **每月網站報表 · %s**"%date.today().strftime("%Y-%m")
if first:
    body=header+"\n\n👁 全部 16 站累計總瀏覽：**%s** 次\n（首次報表，下個月起會顯示每月成長 +N 與估算收入）\n\n"%format(total,",")+"\n".join(lines)
else:
    views=max(dtotal,0)
    body=header+"\n\n👁 總瀏覽 **%s**（本月 +%s）\n\n"%(format(total,","),format(dtotal,","))+"\n".join(lines)+"\n\n💰 估算 AdSense 收入（本月）：約 $%.1f ~ $%.1f\n（聯盟/Ko-fi 請到各後台查看）"%(views/1000.0,views/1000.0*4)
wh=os.environ.get("DISCORD_WEBHOOK")
if wh:
    data=json.dumps({"content":body[:1900]}).encode("utf-8")
    req=urllib.request.Request(wh,data=data,headers={"Content-Type":"application/json","User-Agent":"Mozilla/5.0 (compatible; sm413-report-bot)"})
    urllib.request.urlopen(req,timeout=20); print("posted to discord")
else:
    print("no webhook set")
with open("views_snapshot.json","w",encoding="utf-8") as f:
    json.dump(cur,f,ensure_ascii=False)
print(body)
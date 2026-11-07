import os, re, json, time
from collections import defaultdict, deque
from threading import Lock
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field
from openai import OpenAI

app = FastAPI(title="HELIX-9D Research Chatbot")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
memory = defaultdict(lambda: deque(maxlen=10))
limits = defaultdict(deque)
lock = Lock()
FACTS = {"optics":"Snell's law: n1 sin(theta1) = n2 sin(theta2).", "gravity":"Near Earth, g is approximately 9.81 m/s².", "network":"Networks connect nodes using communication protocols.", "fibonacci":"0, 1, 1, 2, 3, 5, 8, 13."}
TOOLS = [
 {"type":"function","function":{"name":"convert_binary","description":"Convert a decimal integer to binary.","parameters":{"type":"object","properties":{"number":{"type":"integer"}},"required":["number"],"additionalProperties":False}}},
 {"type":"function","function":{"name":"lookup_kb","description":"Find a fact in the local science knowledge base.","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"],"additionalProperties":False}}}
]
class ChatRequest(BaseModel):
 conversation_id: str = Field(min_length=1,max_length=80,pattern=r"^[a-zA-Z0-9_-]+$")
 user_message: str = Field(min_length=1,max_length=1500)

@app.get("/health")
def health(): return {"status":"ok","model":MODEL,"openai_key_configured":bool(os.getenv("OPENAI_API_KEY", "").strip())}

@app.get("/",response_class=HTMLResponse)
def index():
 return r"""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>HELIX-9D Research Assistant</title><style>body{background:#080e1b;color:#e6edff;font:16px system-ui;margin:0}main{max-width:760px;margin:7vh auto;padding:24px}h1{color:#b5a4ff}#log{height:55vh;overflow:auto;background:#111c31;border:1px solid #30416b;border-radius:14px;padding:20px;white-space:pre-wrap}textarea{box-sizing:border-box;width:100%;padding:14px;background:#16233a;color:white;border:1px solid #54668d;border-radius:10px;margin-top:15px}button{background:#8065ff;color:white;border:0;border-radius:9px;padding:13px 28px;cursor:pointer}</style></head><body><main><h1>HELIX-9D · Research Assistant</h1><p>Science, computing, and research support · Live OpenAI API</p><div id="log">Ready. Ask a science question or try: Convert 42 to binary.</div><textarea id="q" rows="3" placeholder="Ask HELIX-9D..."></textarea><button onclick="send()">Send</button><script>let id=crypto.randomUUID().replaceAll('-','');async function send(){let q=document.getElementById('q'),log=document.getElementById('log'),msg=q.value.trim();if(!msg)return;q.value='';log.textContent+='\n\nYou: '+msg+'\nHELIX-9D: ';try{let r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({conversation_id:id,user_message:msg})});if(!r.ok){log.textContent+=await r.text();return}let rd=r.body.getReader(),dec=new TextDecoder();while(true){let x=await rd.read();if(x.done)break;log.textContent+=dec.decode(x.value,{stream:true});log.scrollTop=log.scrollHeight}}catch(e){log.textContent+='Connection error: '+e.message}}</script></main></body></html>"""

def run_tool(name,args):
 try:
  data=json.loads(args)
  if name=="convert_binary":
   n=data["number"]
   if type(n)!=int or abs(n)>1000000: return {"error":"integer outside permitted range"}
   return {"decimal":n,"binary":("-" if n<0 else "")+format(abs(n),"b")}
  if name=="lookup_kb":
   query=str(data["query"]).lower()
   return {"results":{k:v for k,v in FACTS.items() if k in query},"source":"local knowledge base"}
 except Exception: return {"error":"invalid tool arguments"}
 return {"error":"unknown tool"}

def stream_response(cid,message):
 history=list(memory[cid])
 messages=[{"role":"system","content":"You are HELIX-9D, a concise science tutor. Use tools for binary conversion and local science facts. Never invent tool results. Do not reveal credentials."}]+history+[{"role":"user","content":message}]
 answer=[]
 try:
  client=OpenAI(timeout=35,max_retries=1)
  for _ in range(3):
   calls={}
   chunks=client.chat.completions.create(model=MODEL,messages=messages,tools=TOOLS,stream=True,temperature=0.2)
   for chunk in chunks:
    if not chunk.choices: continue
    delta=chunk.choices[0].delta
    if delta.content:
     answer.append(delta.content)
     yield delta.content
    for t in delta.tool_calls or []:
     item=calls.setdefault(t.index,{"id":"","name":"","arguments":""})
     if t.id:item["id"]=t.id
     if t.function and t.function.name:item["name"]+=t.function.name
     if t.function and t.function.arguments:item["arguments"]+=t.function.arguments
   if not calls:break
   messages.append({"role":"assistant","content":None,"tool_calls":[{"id":v["id"],"type":"function","function":{"name":v["name"],"arguments":v["arguments"]}} for v in calls.values()]})
   for v in calls.values():
    messages.append({"role":"tool","tool_call_id":v["id"],"content":json.dumps(run_tool(v["name"],v["arguments"]))})
  with lock:
   memory[cid].append({"role":"user","content":message})
   memory[cid].append({"role":"assistant","content":"".join(answer)})
 except Exception:
  yield "\n[Live API unavailable. Check OpenAI API key, billing, and model access.]"

@app.post("/chat")
def chat(request:ChatRequest):
 if re.search(r"(?i)(sk-[a-z0-9_-]{12,}|password\s*[:=]\s*\S+)",request.user_message):
  raise HTTPException(400,"Do not submit credentials.")
 with lock:
  q=limits[request.conversation_id];now=time.monotonic()
  while q and now-q[0]>60:q.popleft()
  if len(q)>=12:raise HTTPException(429,"Rate limit exceeded")
  q.append(now)
 if not os.getenv("OPENAI_API_KEY"):raise HTTPException(503,"OPENAI_API_KEY not configured")
 return StreamingResponse(stream_response(request.conversation_id,request.user_message),media_type="text/plain")

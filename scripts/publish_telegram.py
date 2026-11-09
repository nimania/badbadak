import json,os,re,html,sys,time,argparse,datetime as dt,urllib.request,urllib.parse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT/'data/telegram-published.json'
SOURCES=[('featured-news.json','featured'),('stories.json','story'),('meshki-news-feed.json','meshki'),('bartarinha-feed.json','external'),('rokna-feed.json','external'),('7sobh-feed.json','external')]
MATCH=re.compile('بازیگر|خواننده|سینما|سریال|هنرمند|کنسرت|سلبریتی|فیلم|چهره|آرایش|زیبایی|پوست|پوشاک|لباس|استایل|فشن|خوراک|غذا|رستوران|آشپزی|قهوه|شیرینی|سلامت|پزشکی|بیماری|درمان|گردشگری|هتل|سفر|فناوری|تکنولوژی|گجت|آیفون|حادثه|تصادف|آتش.?سوزی|جنجال|حاشیه|قتل|شهربازی|عروسی|ازدواج|طلاق|فیلیمو|فیلم.?نت|نماوا')
BLOCK=re.compile('نفتکش|سپاه|موشک|حمله نظامی|تنگه هرمز|غزه|انتخابات|نتانیاهو|کنست|انصارالله|جنگ|سفیر|دیپلمات|وزیر|رئیس.?جمهور|جاسوسی|تروریست|پایگاه نظامی|ناتو')
def read(p,default):
 try:return json.loads(p.read_text(encoding='utf-8'))
 except (OSError,ValueError):return default
def date(s):
 try:
  d=dt.datetime.fromisoformat(str(s).replace('Z','+00:00'))
  return d.replace(tzinfo=dt.timezone.utc) if d.tzinfo is None else d.astimezone(dt.timezone.utc)
 except (TypeError,ValueError):return None
def collect():
 out={}
 now=dt.datetime.now(dt.timezone.utc)
 for filename,kind in SOURCES:
  raw=read(ROOT/'data'/filename,[])
  rows=raw.get('items',[]) if isinstance(raw,dict) else raw
  if not isinstance(rows,list):continue
  for o in rows:
   if not isinstance(o,dict):continue
   title=str(o.get('headline_fa') or o.get('titleFa') or o.get('title') or '').strip()
   uid=str(o.get('id') or o.get('url') or '').strip()
   if not title or not uid:continue
   if kind not in ('featured','meshki') and not (o.get('bb_category') or MATCH.search(title)):continue
   if BLOCK.search(title) and not re.search('بازیگر|خواننده|هنرمند',title):continue
   stamp=date(o.get('published_at') or o.get('published') or o.get('last_seen'))
   if not stamp or not now-dt.timedelta(hours=72)<=stamp<=now+dt.timedelta(hours=1):continue
   if kind=='meshki':
    if not o.get('page') or not o.get('titleFa'):continue
    link='https://meshki.media/haber/'+urllib.parse.quote(uid,safe='')+'/'
    image=o.get('image')
   elif kind in ('featured','story'):
    link='https://nimania.github.io/badbadak/news/'+re.sub('[^A-Za-z0-9_-]','_',uid)+'/'
    image=o.get('image_url')
   else:
    link=o.get('url');image=o.get('image')
   if not isinstance(link,str) or not link.startswith('https://'):continue
   key=kind+':'+uid
   out[key]={'key':key,'title':title,'summary':str(o.get('summary_fa') or o.get('summaryFa') or o.get('summary') or ''),'link':link,'image':image,'date':stamp}
 return sorted(out.values(),key=lambda x:(x['date'],x['key']))
def call(token,method,values):
 req=urllib.request.Request('https://api.telegram.org/bot'+token+'/'+method,data=urllib.parse.urlencode(values).encode(),headers={'Content-Type':'application/x-www-form-urlencoded'})
 with urllib.request.urlopen(req,timeout=25) as resp:result=json.load(resp)
 if not result.get('ok'):raise RuntimeError(str(result.get('description')))
 return result['result']
def message(o):
 title=html.escape(o['title'][:180])
 summary=re.sub('\\s+',' ',re.sub('<[^>]*>','',o['summary'])).strip()
 if len(summary)>440:summary=summary[:440].rstrip(' ،؛')+'…'
 return '🪁 <b>'+title+'</b>'+ ('\n\n'+html.escape(summary) if summary else '')+'\n\n🔗 <a href="'+html.escape(o['link'],quote=True)+'">متن کامل و منبع</a>\n\n@badbadakmedia'
def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--test',action='store_true',help='Send one verification post to the Badbadak channel')
 parser.add_argument('--discover',action='store_true',help='Read a channel verification post from Telegram updates')
 args=parser.parse_args()
 if args.discover:
  token=os.getenv('NESHANIKERMAN_BOT_TOKEN','')
  if not token:sys.exit('Missing NESHANIKERMAN_BOT_TOKEN secret')
  me=call(token,'getMe',{})
  if me.get('username','').lower()!='neshanikermanbot':sys.exit('Wrong bot account')
  updates=call(token,'getUpdates',{'limit':100,'timeout':0,'allowed_updates':json.dumps(['channel_post'])})
  found=[]
  for update in updates:
   post=update.get('channel_post',{})
   chat=post.get('chat',{})
   body=post.get('text','')
   if 'آزمایش اتصال بادبادک' in body and chat.get('type')=='channel':
    found.append({'channel_id':chat.get('id'),'username':chat.get('username'),'title':chat.get('title')})
  print('Matching channel verification posts:',json.dumps(found,ensure_ascii=False))
  return
 if args.test:
  token=os.getenv('NESHANIKERMAN_BOT_TOKEN','')
  if not token:sys.exit('Missing NESHANIKERMAN_BOT_TOKEN secret')
  me=call(token,'getMe',{})
  if me.get('username','').lower()!='neshanikermanbot':sys.exit('Wrong bot account')
  member=call(token,'getChatMember',{'chat_id':'-1004451374854','user_id':me['id']})
  if member.get('status') not in ('administrator','creator') or (member.get('status')=='administrator' and not member.get('can_post_messages',False)):sys.exit('Bot needs permission to post')
  sent=call(token,'sendMessage',{'chat_id':'-1004451374854','text':'🪁 پیام آزمایشی بادبادک\n\nاتصال انتشار خودکار بادبادک به این کانال با موفقیت آزمایش شد.\n\n@badbadakmedia'})
  print('Telegram test sent; message_id:',sent['message_id'])
  return
 state=read(STATE,{})
 seen=state.get('published',{}) if isinstance(state,dict) else {}
 candidates=collect()
 if not STATE.exists():
  seen.update({x['key']:'bootstrap' for x in candidates})
  STATE.write_text(json.dumps({'published':seen},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  print('Initialized without sending archived news:',len(candidates));return
 pending=[x for x in candidates if x['key'] not in seen]
 if not pending:print('No new items');return
 token=os.getenv('NESHANIKERMAN_BOT_TOKEN','')
 if not token:sys.exit('Missing NESHANIKERMAN_BOT_TOKEN secret; no posts sent')
 me=call(token,'getMe',{})
 if me.get('username','').lower()!='neshanikermanbot':sys.exit('Wrong bot account; no posts sent')
 member=call(token,'getChatMember',{'chat_id':'-1004451374854','user_id':me['id']})
 if member.get('status') not in ('administrator','creator') or (member.get('status')=='administrator' and not member.get('can_post_messages',False)):sys.exit('Bot needs channel post permission')
 failures=0
 for o in pending[:8]:
  base={'chat_id':'-1004451374854','parse_mode':'HTML'}
  try:
   photo=o['image']
   if isinstance(photo,str) and photo.startswith('https://'):
    try:result=call(token,'sendPhoto',dict(base,photo=photo,caption=message(o)))
    except Exception as e:
     print('Photo failed, using text:',str(e)[:120])
     result=call(token,'sendMessage',dict(base,text=message(o)))
   else:result=call(token,'sendMessage',dict(base,text=message(o)))
   seen[o['key']]={'message_id':result['message_id'],'posted_at':dt.datetime.now(dt.timezone.utc).isoformat()}
   STATE.write_text(json.dumps({'published':seen},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
   print('Published',o['key']);time.sleep(1)
  except Exception as e:
   failures+=1;print('Failed',o['key'],str(e)[:200],file=sys.stderr)
 if failures:sys.exit(1)
if __name__=='__main__':main()

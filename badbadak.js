/* Badbadak: tabloid newspaper lens over Pendar's existing datasets. */
const BB_CATEGORIES = [ ['all','همه'], ['celeb','سلبریتی'], ['turkish','سریال‌های ترکی'], ['beauty','آرایش و زیبایی'], ['health','سلامت'], ['style','مُد و استایل'], ['food','خوراکی'], ['buzz','جنجال و حوادث'], ['tech','تکنولوژی'], ['travel','سفر'] ];
let _badbadakLoaded=false, _bbLoading=null, _bbStories=[], _bbPeople=[], _bbTrends=[], _bbCategory='all', _bbMeshkiNews=[], _bbBartarinha=[], _bbRokna=[], _bb7sobh=[], _bbSeries=[], _bbPage='home';

function bbCategory(s){
 if(s.bb_category)return s.bb_category;
 const t=s.headline_fa||s.title_fa||s.title||'';
 if(/نفتکش|سپاه|موشک|حمله نظامی|تنگه هرمز|غزه|جنگ|سفیر|دیپلمات|وزیر|رئیس‌جمهور|جاسوسی|تروریست|پایگاه نظامی|ناتو/.test(t)&&!/بازیگر|خواننده|هنرمند/.test(t))return null;
 for(const [key,re] of [['celeb',/بازیگر|خواننده|سینما|سریال|هنرمند|کنسرت|سلبریتی|جشنواره.*فیلم|منوچهر هادی|یکتا ناصر/],['beauty',/آرایش|زیبایی|پوست(?:\s|$)|موهای|مراقبت.*مو/],['food',/خوراک|غذا|رستوران|آشپزی|تغذیه|قهوه|شیرینی/],['style',/پوشاک|لباس|استایل|فشن|طراح.*مد/],['health',/سلامت|پزشکی|بیماری|درمان|بهداشت|طاعون/],['travel',/گردشگری|هتل|مقصد.*سفر/],['tech',/فناوری|هوش مصنوعی|تکنولوژی|گجت|آیفون/],['buzz',/حادثه|تصادف|آتش.سوزی|جنجال|حاشیه|قتل|شهربازی/]])if(re.test(t))return key;
 return null;
}
function bbLabel(k){return BB_CATEGORIES.find(c=>c[0]===k)?.[1]||'تازه‌ها';}
function bbSafeImage(u){return typeof u==='string'&&(/^(https?:\/\/|assets\/)/.test(u))?u:'';}
function bbStoryURL(s){return s.bb_url||routeURL('#/story/'+encodeURIComponent(s.id));}

const BB_HEADLINES={
 'aed86c62-6776-4969-933d-d5282283e40c':'گوشی سیاوش طهمورث به صاحبش برگشت',
 'dfe90678-c013-4669-b7ba-693accda0995':'یکتا ناصر و منوچهر هادی کنار هم',
 '3e7597d0-9ecb-44ee-9780-356a270a3133':'تازه‌های جشنواره‌های فیلم کودک و کوتاه',
 '60ad07b4-83ec-4f56-b908-c910c4ae9d0c':'ابهام درباره مرگ کارمند آزمایشگاه روسیه',
 '697815e5-7ef7-428d-a894-ec02a2cb0b26':'پنج شهربازی تهران به‌دلیل ناایمنی پلمب شدند',
 '64faa629-b111-4e2d-80a6-37c465380ce4':'خبری از طاعون در سیبری نیست',
 '31de2f51-892f-43e3-92ca-11235971914d':'قتل مرد سالخورده در آتش‌سوزی عمدی',
 '1bc87eda2eb8':'پست تازه جمره بایسل خبرساز شد',
 '9329ad9570e2':'مرگ عزیز، خانواده «حیثیت» را آشفت',
 '70a31f2a4a8d':'روایت اوزوناتاغان از عشقی ده‌ساله',
 '4e032ca43bce':'معرفی‌نامه تازه سریال «عشق احتمالی» منتشر شد',
 'dcaa785a08a2':'تصاویر عاشقانه مروه دینچکول و همسرش',
 '6e318a537fee':'جشن چهارسالگی دختر مورات ییلدیریم',
 '11296e08bb33':'واکنش تورکان شورای به درگذشت ارسوی',
 '04570dd9dbff':'عکس کودکی پلین کاراهان خبرساز شد',
 '709cfe7b7189':'جشن چهارسالگی دختر مورات ییلدیریم',
 '3ac621b46c9e':'رنگ موی تازه نیلپری شاهین‌کایا',
 '693020f42e63':'پیش‌نمایش قسمت پنجم «سِودان بیر آتش»',
 'e150ce5f4e9f':'داماد روز عروسی خانه را اشتباه رفت',
 'b7e23b1d2ac9':'دمی رز ناگهان ناپدید شد',
 'd938529a4313':'ویدیوی عاشقانه بانو آلکان در هلند',
 'b54e0a588663':'مهمانی نازلی صابانجی برای فرزندش',
 '1d37134e6f2c':'لحظات شاد عزیز پیش از مرگ',
 'c4c8143a7f0a':'تغییرات بزرگ در سوروایور ۲۰۲۷'
};

function bbHeadline(s){
 let title=BB_HEADLINES[s.id]||s.headline_fa||'تازه‌های امروز در بادبادک';
 title=title.replace(/^(?:گزارش‌هایی درباره|گزارش‌هایی از|گزارش درباره|انتشار گزارش|بر اساس گزارش‌ها|اعلام خبر)\s+/,'').replace(/\s+/g,' ').trim();
 const words=title.split(/\s+/);
 if(words.length<=7)return title;
 const clause=title.split(/[؛؛:!?؟]/)[0].trim().split(/\s+/);
 let brief=(clause.length>=4?clause:words).slice(0,7);
 while(brief.length>4&&/^(و|از|به|با|در|برای|درباره|که|را)$/.test(brief.at(-1)))brief.pop();
 return brief.join(' ').replace(/[،؛:]$/,'')+'…';
}
function bbStoryImage(s){return bbSafeImage(s.image_url)||bbSafeImage(s.bb_fallback_image);}
function bbImageError(img){
 const story=[..._bbStories,..._bbMeshkiNews].find(s=>s.image_url===img.getAttribute('src'));
 const fallback=bbSafeImage(story?.bb_fallback_image);
 if(fallback&&img.getAttribute('src')!==fallback){img.src=fallback;return;}
 img.hidden=true;
}

/* === Persian date helper === */
function bbPersianDate(){
 try {
  const d=new Date();
  const f=new Intl.DateTimeFormat('fa-IR',{weekday:'long',year:'numeric',month:'long',day:'numeric',timeZone:'Asia/Tehran'});
  return f.format(d);
 } catch(_) { return ''; }
}

/* === SHOW / LOAD === */
function showBadbadak(){_bbPage='home';show('badbadak');setTab('');setHash('#/badbadak');document.title='بادبادک | چهره‌ها، سبک زندگی و سرگرمی | پندار';return renderBadbadak();}

async function renderBadbadak(){
 if(_badbadakLoaded){bbRender();return;}
 if(_bbLoading)return _bbLoading;
 const el=document.getElementById('badbadak-content');el.innerHTML='<div class="state" role="status">در حال آوردن تازه‌های بادبادک…</div>';
 _bbLoading=(async()=>{
 try{
 const results=await Promise.allSettled([ALL.length?Promise.resolve(ALL):getJSON(`${DATA}/stories.json`),getJSON(`${DATA}/figures.json`),getJSON(`${DATA}/entity-registry.json`),getJSON(`${DATA}/trends.json`),getJSON(`${DATA}/meshki-news-feed.json`,8000),loadMeshkiSeries(),getJSON(`${DATA}/bartarinha-feed.json`,8000),getJSON(`${DATA}/rokna-feed.json`,8000),getJSON(`${DATA}/7sobh-feed.json`,8000)]);
 if(results[0].status!=='fulfilled'&&results[4].status!=='fulfilled'&&![6,7,8].some(i=>results[i].status==='fulfilled'&&Array.isArray(results[i].value)&&results[i].value.length))throw new Error('stories');
 const data=results[0].status==='fulfilled'?results[0].value:[];const stories=Array.isArray(data)?data:data.stories||[];
 const now=Date.now();const age=s=>Math.max(0,(now-Date.parse(s.last_seen||s.published_at||s.first_seen||''))/86400000)||0;
 _bbStories=stories.filter(s=>s.id&&bbCategory(s)).sort((a,b)=>(Math.log2(1+(b.source_count||1))*3-age(b)+(bbCategory(b)==='celeb'?5:0))-(Math.log2(1+(a.source_count||1))*3-age(a)+(bbCategory(a)==='celeb'?5:0))).slice(0,120);
 const figures=results[1].status==='fulfilled'?results[1].value:{};
 const registry=results[2].status==='fulfilled'?results[2].value:{};
 const entities=Array.isArray(registry)?registry:Array.isArray(registry.entities)?registry.entities:Object.values(registry.entities||{});
 const meshki=results[4].status==='fulfilled'?results[4].value:{};
 const seen=new Set();
 _bbMeshkiNews=(meshki.items||[]).filter(n=>n.titleFa&&n.page&&bbSafeImage(n.image)&&!/[a-zA-Z]{3,}/.test(n.titleFa)).filter(n=>{const key=n.titleFa.replace(/[\s‌،؛«»]/g,'');if(seen.has(key))return false;seen.add(key);return true;}).sort((a,b)=>String(b.published||'').localeCompare(String(a.published||''))).slice(0,12).map(n=>({id:n.id,headline_fa:n.titleFa,summary_fa:n.summaryFa,image_url:n.image,published_at:n.published,source_count:(n.sources||[]).length||1,bb_category:'turkish',bb_url:MESHKI_ROOT+'haber/'+encodeURIComponent(n.id)+'/'})).filter((n,i,rows)=>rows.findIndex(x=>bbHeadline(x)===bbHeadline(n))===i);
 const bartarinhaRaw=results[6].status==='fulfilled'?(Array.isArray(results[6].value)?results[6].value:[]):[];
 const btSeen=new Set();
 _bbBartarinha=bartarinhaRaw.filter(n=>n.title&&n.url).filter(n=>{const key=n.title.replace(/[\s‌،؛«»]/g,'');if(btSeen.has(key))return false;btSeen.add(key);return true;}).sort((a,b)=>String(b.published||'').localeCompare(String(a.published||''))).slice(0,15).map(n=>({id:n.id||n.url,headline_fa:n.title,summary_fa:n.summary||'',image_url:n.image||'',published_at:n.published||'',source_count:1,bb_category:bbCategory({headline_fa:n.title})||'buzz',bb_url:n.url,bb_source:'bartarinha.ir'}));
 const roknaRaw=results[7].status==='fulfilled'?(Array.isArray(results[7].value)?results[7].value:[]):[];
 const rkSeen=new Set();
 _bbRokna=roknaRaw.filter(n=>n.title&&n.url).filter(n=>{const key=n.title.replace(/[\s‌،؛«»]/g,'');if(rkSeen.has(key))return false;rkSeen.add(key);return true;}).sort((a,b)=>String(b.published||'').localeCompare(String(a.published||''))).slice(0,15).map(n=>({id:n.id||n.url,headline_fa:n.title,summary_fa:n.summary||'',image_url:n.image||'',published_at:n.published||'',source_count:1,bb_category:bbCategory({headline_fa:n.title})||'buzz',bb_url:n.url,bb_source:'رکنا'}));
 const sobhRaw=results[8].status==='fulfilled'?(Array.isArray(results[8].value)?results[8].value:[]):[];
 const shSeen=new Set();
 _bb7sobh=sobhRaw.filter(n=>n.title&&n.url).filter(n=>{const key=n.title.replace(/[\s‌،؛«»]/g,'');if(shSeen.has(key))return false;shSeen.add(key);return true;}).sort((a,b)=>String(b.published||'').localeCompare(String(a.published||''))).slice(0,15).map(n=>({id:n.id||n.url,headline_fa:n.title,summary_fa:n.summary||'',image_url:n.image||'',published_at:n.published||'',source_count:1,bb_category:bbCategory({headline_fa:n.title})||'buzz',bb_url:n.url,bb_source:'هفت صبح'}));
 _bbSeries=(results[5].status==='fulfilled'?results[5].value.rows:[]).filter(r=>r.status==='در حال پخش'&&bbSafeImage(r.hero)).slice(0,10);
 for(const story of _bbStories){
  const names=(story.entities||[]).map(e=>e.name_fa).filter(Boolean);
  const person=entities.find(e=>e.type==='person'&&names.includes(e.name_fa)&&bbSafeImage(e.meta?.avatar));
  if(person)story.bb_fallback_image=person.meta.avatar;
 }
 const names=[..._bbStories,..._bbMeshkiNews,..._bbBartarinha,..._bbRokna,..._bb7sobh].map(s=>s.headline_fa||'').join(' ');
 _bbPeople=[...(figures.figures||[]).map(f=>({...f,bbURL:routeURL('#/figure/'+encodeURIComponent(f.handle))})),...entities.filter(e=>e.type==='person'||e.kind==='person').map(e=>({...e,name_fa:e.name_fa||e.title,avatar:e.meta?.avatar||e.image_url||e.avatar||e.image?.path,bbURL:routeURL('#/entity/'+encodeURIComponent(e.id))}))].filter(p=>p.name_fa&&bbSafeImage(p.avatar)&&names.includes(p.name_fa)).filter((p,i,arr)=>arr.findIndex(x=>x.name_fa===p.name_fa)===i).slice(0,14);
 const trends=results[3].status==='fulfilled'?results[3].value:[];_bbTrends=(Array.isArray(trends)?trends:trends.trends||[]).filter(t=>t.id&&bbCategory(t)).slice(0,4);
 _badbadakLoaded=true;if(_bbPage==='home')bbRender();
 }catch(e){if(_bbPage!=='home')return;el.innerHTML='<div class="state"><h2>تازه‌ها هنوز نرسیده‌اند</h2><p>دریافت خبرها انجام نشد.</p><button type="button" onclick="renderBadbadak()">تلاش دوباره</button></div>';}
 finally{_bbLoading=null;}
 })();return _bbLoading;
}

function bbFilter(k){_bbCategory=k;bbRender();}

/* === Source badge for external stories === */
function bbSourceTag(s){
 if(s.bb_source) return `<span class="bb-source-tag">${esc(s.bb_source)}</span>`;
 if(s.bb_category==='turkish'&&s.bb_url) return '<span class="bb-source-tag">مشکی‌مدیا</span>';
 return '';
}

/* === Cell builder helpers === */
function bbCellLink(s, inner, cls=''){
 const url=bbStoryURL(s);
 const ext=s.bb_url?' target="_blank" rel="noopener"':'';
 return `<a href="${esc(url)}"${ext}>${inner}</a>`;
}
function bbImgTag(s, cls='bb-photo', extra=''){
 const src=bbStoryImage(s);
 if(!src) return '';
 return `<img class="${cls}" src="${esc(src)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="bbImageError(this)" ${extra}>`;
}

/* === Numbered list item (for "bours akhbar" style) === */
function bbNumberedItem(s, num){
 const badge = ['۱','۲','۳','۴','۵','۶','۷','۸','۹','۱۰'][num-1]||String(num);
 return `<div style="display:flex; align-items:flex-start; gap:6px; margin-bottom:6px;">
  <span class="bb-num-badge">${badge}</span>
  ${bbCellLink(s, `<span class="bb-headline-sm">${esc(bbHeadline(s))}</span>${bbSourceTag(s)}`)}
 </div>`;
}

/* === MAIN RENDER === */
function bbRender(){
 if(_bbPage!=='home')return;
 const _extNews=[..._bbMeshkiNews,..._bbBartarinha,..._bbRokna,..._bb7sobh].sort((a,b)=>String(b.published_at||'').localeCompare(String(a.published_at||'')));
 const combined=_bbStories.flatMap((s,i)=>_extNews[i]?[s,_extNews[i]]:[s]).concat(_extNews.slice(_bbStories.length));
 const stories=combined.filter(s=>_bbCategory==='all'||bbCategory(s)===_bbCategory);
 const hero=stories[0];
 const popular=[...stories].sort((a,b)=>(b.source_count||0)-(a.source_count||0)).slice(0,5);
 const s=stories; // shorthand

 document.getElementById('badbadak-content').innerHTML=`
 <div class="bb-newspaper">
  <!-- MASTHEAD -->
  <div class="bb-masthead">
   <div class="bb-masthead-logo">
    <img src="assets/badbadak-logo.png" alt="" width="36" height="36">
    بادبادک
   </div>
   <div class="bb-masthead-center">چهره‌ها · سبک زندگی · سرگرمی</div>
   <div class="bb-masthead-meta">
    <span class="bb-edition">ضمیمهٔ پندار</span>
    <span>${bbPersianDate()}</span>
   </div>
  </div>

  <!-- TICKER -->
  ${hero?`<div class="bb-ticker">
   <span>🔥 ${esc(bbHeadline(hero))}</span>
   ${s[1]?`<span>${esc(bbHeadline(s[1]))}</span>`:''}
   ${s[2]?`<span>${esc(bbHeadline(s[2]))}</span>`:''}
  </div>`:''}

  <!-- PILLS -->
  <div class="bb-pills" role="group" aria-label="موضوع خبرها">${BB_CATEGORIES.map(([k,label])=>`<button type="button" aria-pressed="${k===_bbCategory}" onclick="bbFilter('${k}')">${label}</button>`).join('')}</div>

  ${_bbPeople.length?`<div class="bb-celeb-strip">${_bbPeople.map(p=>`<a href="${esc(p.bbURL)}"><img src="${esc(p.avatar)}" alt="" loading="lazy" onerror="this.hidden=true"><span>${esc(p.name_fa)}</span></a>`).join('')}</div>`:''}

  <!-- ROW 1: HERO + SIDEBAR -->
  ${hero?`<div class="bb-grid">
   <div class="bb-cell bb-cell-hero bb-cell-yellow">
    ${bbCellLink(hero, `
     <div class="bb-kicker">${esc(bbLabel(bbCategory(hero)))} · گزارش ویژه</div>
     <h1 class="bb-headline-mega">${esc(bbHeadline(hero))}</h1>
     ${bbSourceTag(hero)}
     ${hero.summary_fa?`<p class="bb-lead">${esc(hero.summary_fa.slice(0,200))}</p>`:''}
     ${bbImgTag(hero, 'bb-photo bb-photo-wide', 'fetchpriority="high"')}
    `)}
   </div>
   ${s[1]?`<div class="bb-cell bb-cell-side-top">
    ${bbCellLink(s[1], `
     <span class="bb-tag bb-tag-hot">${esc(bbLabel(bbCategory(s[1])))}</span>
     <h2 class="bb-headline-lg">${esc(bbHeadline(s[1]))}</h2>
     ${s[1].summary_fa?`<p class="bb-lead">${esc(s[1].summary_fa.slice(0,120))}</p>`:''}
    `)}
   </div>`:''}
   ${s[2]?`<div class="bb-cell bb-cell-side-bottom">
    <span class="bb-tag bb-tag-yellow">${esc(bbLabel(bbCategory(s[2])))}</span>
    ${bbImgTag(s[2], 'bb-photo', 'style="aspect-ratio:4/3"')}
    ${bbCellLink(s[2], `<h2 class="bb-headline-md">${esc(bbHeadline(s[2]))}</h2>`)}
   </div>`:''}
  </div>`:''}

  <!-- ROW 2: 3 cells (2+2+2) — numbered popular + featured + guide -->
  ${popular.length?`<div class="bb-grid">
   <div class="bb-cell bb-span-2 bb-cell-dark">
    <div class="bb-kicker">بورس اخبار</div>
    <h2 class="bb-headline-lg" style="color:var(--bb-yellow);">پربازتاب‌ترین‌ها</h2>
    <hr class="bb-sep">
    ${popular.slice(0,3).map((p,i)=>bbNumberedItem(p,i+1)).join('')}
   </div>
   <div class="bb-cell bb-span-2 bb-cell-yellow">
    ${s[3]?bbCellLink(s[3], `
     <span class="bb-tag bb-tag-hot">${esc(bbLabel(bbCategory(s[3])))}</span>
     ${bbImgTag(s[3], 'bb-photo', 'style="aspect-ratio:16/9"')}
     <h2 class="bb-headline-lg">${esc(bbHeadline(s[3]))}</h2>
     ${s[3].summary_fa?`<p class="bb-lead">${esc(s[3].summary_fa.slice(0,150))}</p>`:''}
    `):''}
   </div>
   <div class="bb-cell bb-span-2">
    ${s[4]&&s[5]?`
     <div class="bb-kicker">تازه‌ها</div>
     ${bbCellLink(s[4], `<h2 class="bb-headline-md">${esc(bbHeadline(s[4]))}</h2>`)}
     <hr class="bb-sep">
     ${bbCellLink(s[5], `<h2 class="bb-headline-md">${esc(bbHeadline(s[5]))}</h2>`)}
     ${s[6]?`<hr class="bb-sep">${bbCellLink(s[6], `<h2 class="bb-headline-md">${esc(bbHeadline(s[6]))}</h2>`)}`:''}
    `:''}
   </div>
  </div>`:''}

  <!-- ROW 3: 2 cells (3+3) — quote + trivia -->
  <div class="bb-grid">
   ${s[7]?`<div class="bb-cell bb-span-3 bb-cell-dark">
    <div class="bb-kicker">گفته‌ها و دیدگاه‌ها</div>
    ${bbCellLink(s[7], `
     <div class="bb-pull-quote" style="color:var(--bb-yellow); border-color:var(--bb-yellow);">«${esc(bbHeadline(s[7]))}»</div>
     ${s[7].summary_fa?`<p class="bb-lead">${esc(s[7].summary_fa.slice(0,160))}</p>`:''}
    `)}
   </div>`:''}
   <div class="bb-cell bb-span-3 bb-cell-yellow">
    <div class="bb-horoscope">
     <h2 class="bb-headline-lg">فال امروز، برای سرگرمی</h2>
     <div class="bb-horo-strip">${['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند'].map((m,i)=>`<button type="button" onclick="bbHoroscope(${i},this)" aria-pressed="false"><span class="bb-horo-icon">${['♈','♉','♊','♋','♌','♍','♎','♏','♐','♑','♒','♓'][i]}</span>${m}</button>`).join('')}</div>
     <p id="bb-horo-result" aria-live="polite">ماه تولدت را انتخاب کن.</p>
    </div>
   </div>
  </div>

  <!-- ROW 4: 3 cells — more stories -->
  <div class="bb-grid">
   ${s.slice(8,11).map((st,i)=>{
    const cls = i===1 ? 'bb-cell-dark' : i===2 ? 'bb-cell-yellow' : '';
    return `<div class="bb-cell bb-span-2 ${cls}">
     ${bbCellLink(st, `
      <span class="bb-tag${i===1?' bb-tag-hot':''}">${esc(bbLabel(bbCategory(st)))}</span>
      ${bbImgTag(st, 'bb-photo-sm')}
      <h2 class="bb-headline-md">${esc(bbHeadline(st))}</h2>
      ${bbSourceTag(st)}
      ${st.summary_fa?`<p class="bb-lead">${esc(st.summary_fa.slice(0,120))}</p>`:''}
     `)}
    </div>`;
   }).join('')}
  </div>

  <!-- SERIES STRIP -->
  ${bbSeriesSection()}

  <!-- ROW 5: More stories grid -->
  ${s.length>11?`<div class="bb-grid">
   ${s.slice(11,17).map((st,i)=>{
    const cls = i%3===0 ? 'bb-cell-dark' : i%3===2 ? 'bb-cell-yellow' : '';
    return `<div class="bb-cell bb-span-2 ${cls}">
     ${bbCellLink(st, `
      <span class="bb-tag">${esc(bbLabel(bbCategory(st)))}</span>
      <h2 class="bb-headline-md">${esc(bbHeadline(st))}</h2>
      ${bbSourceTag(st)}
     `)}
    </div>`;
   }).join('')}
  </div>`:''}

  <!-- ROW 6: Poll + Game + Links -->
  <div class="bb-grid">
   <div class="bb-cell bb-span-2">
    <div class="bb-kicker">نظرسنجی</div>
    <h2 class="bb-headline-md">دوست داری بیشتر چه بخوانی؟</h2>
    <div class="bb-poll-options" id="bb-poll-options"></div>
   </div>
   <div class="bb-cell bb-span-2">
    <a class="bb-game-card" href="/badbadak/crossword/">
     <span class="bb-game-icon" aria-hidden="true">▦</span>
     <strong>جدول کلمات متقاطع</strong>
    </a>
    <hr class="bb-sep">
    <div class="bb-kicker">وقت تماشا و خواندن</div>
    <a href="/movies/" style="display:block;margin:4px 0;"><span class="bb-headline-sm">🎬 جان فیلم</span></a>
    <a href="/tv/" style="display:block;margin:4px 0;"><span class="bb-headline-sm">📺 راهنمای تماشا</span></a>
    <a href="/books/" style="display:block;margin:4px 0;"><span class="bb-headline-sm">📚 پیشخوان کتاب</span></a>
   </div>
   <div class="bb-cell bb-span-2 bb-cell-dark">
    ${s.length>17?`
     <div class="bb-kicker">بیشتر بخوانید</div>
     ${s.slice(17,21).map(st=>bbCellLink(st, `<div class="bb-headline-sm" style="margin-bottom:6px;">${esc(bbHeadline(st))}</div>`)).join('<hr class="bb-sep">')}
    `:`
     <div class="bb-kicker">بیشتر بخوانید</div>
     ${popular.slice(3,5).map(st=>bbCellLink(st, `<div class="bb-headline-sm" style="margin-bottom:6px;">${esc(bbHeadline(st))}</div>`)).join('<hr class="bb-sep">')}
    `}
   </div>
  </div>

  <!-- BOTTOM BAR -->
  <div class="bb-bottom-bar">
   <div><a href="/badbadak/">بادبادک</a> — ضمیمهٔ <a href="/">پندار</a></div>
   <div style="opacity:0.6;">چهره‌ها · سبک زندگی · سرگرمی · پیشخوان کتاب · جان‌فیلم · راهنمای تماشا</div>
  </div>
 </div>`;

 bbPollRender();
}

/* === POLL === */
function bbPollRender(){
 const el=document.getElementById('bb-poll-options');
 if(!el)return;
 let choice='';try{choice=localStorage.getItem('bb-poll-v1')||'';}catch(_){}
 el.innerHTML=['چهره‌ها و سرگرمی','خوراکی و سفر','زیبایی و استایل','سلامت و تکنولوژی'].map((s,i)=>`<button type="button" aria-pressed="${choice===String(i)}" onclick="bbVote(${i})">${choice===String(i)?'✓ ':''}${s}</button>`).join('');
}
function bbVote(i){try{localStorage.setItem('bb-poll-v1',String(i));}catch(_){}bbPollRender();}

/* === HOROSCOPE === */
function bbHoroscope(i,button){
 const lines=['یک گفت‌وگوی عقب‌افتاده را شروع کن.','امروز برای یک خوشی کوچک وقت بگذار.','یک ایده را یادداشت کن؛ شاید فردا به کارت بیاید.','به کسی که دلت برایش تنگ شده پیام بده.','کاری را که دوست داری از قدم کوچک شروع کن.','جای یک چیز اضافه را خالی کن.','برای خودت هم به اندازه دیگران وقت بگذار.','امروز یک مسیر تازه را امتحان کن.','یک کتاب یا فیلم تازه کشف کن.','برنامه‌ات را کمی سبک‌تر بچین.','یک آهنگ قدیمی را دوباره گوش کن.','برای یک دیدار دوستانه وقت پیدا کن.'];
 const day=new Intl.DateTimeFormat('en',{timeZone:'Asia/Tehran',day:'numeric'}).format(new Date());
 document.querySelectorAll('.bb-horo-strip button').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
 document.getElementById('bb-horo-result').textContent=lines[(i+Number(day))%12];
}

/* === SERIES SECTION === */
function bbSeriesSection(){
 if(!_bbSeries.length||!['all','celeb','turkish'].includes(_bbCategory))return '';
 return `<div class="bb-series-section">
  <div class="bb-section-title">امشب با سریال‌های ترکی</div>
  <div class="bb-series-strip">${_bbSeries.map(r=>`<a class="bb-series-card" href="${esc(MESHKI_ROOT+'dizi/'+encodeURIComponent(r.slug)+'/')}" target="_blank" rel="noopener"><img src="${esc(r.hero)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.hidden=true"><strong>${esc(r.titleFa||r.titleTr)}</strong><span>${esc(r.airing||r.day||'')}</span></a>`).join('')}</div>
 </div>`;
}

/* === CROSSWORD === */
function showBadbadakCrossword(){
 _bbPage='crossword';show('badbadak');setTab('');setHash('#/badbadak/crossword');document.title='جدول کلمات متقاطع | بادبادک | پندار';
 document.getElementById('badbadak-content').innerHTML='<div class="bb-newspaper"><div class="bb-masthead"><div class="bb-masthead-logo"><img src="assets/badbadak-logo.png" alt="" width="36" height="36"> بادبادک</div><div class="bb-masthead-center">جدول کلمات متقاطع</div><div class="bb-masthead-meta"><a href="/badbadak/" style="color:var(--bb-yellow);">بازگشت</a></div></div><div class="bb-crossword"><div class="bb-game-heading"><div><h2>جدول کلمات متقاطع</h2><p>یک جدول انتخاب کن و شروع کن.</p></div></div><iframe title="بازی جدول کلمات فارسی" src="https://blankuapp.github.io/PersianCrossword/" allow="fullscreen" sandbox="allow-scripts allow-same-origin allow-forms allow-popups" referrerpolicy="no-referrer"></iframe><p style="font-size:.82rem;color:var(--ink-soft);padding:8px 0;"><a href="https://blankuapp.github.io/PersianCrossword/" target="_blank" rel="noopener">نمای تمام‌صفحه</a> · جدول کلمات فارسی</p></div></div>';
}

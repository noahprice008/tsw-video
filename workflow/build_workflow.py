"""Builds the importable n8n workflow: TSW_Daily_Videos.json"""
import json, uuid, pathlib

HERE = pathlib.Path(__file__).parent
ANON = (pathlib.Path("/tmp/anon.txt").read_text().strip())
SUPA = "https://bshvxxzyueimkmhvdtec.supabase.co"
ICONS = "taxi, plane, hotel, phone, passport, shield, map, pin, check, clock, calendar, search, train, storm, sun, wave, fire, alert, money, bag, nowifi, pharmacy, globe, people, lock, camera, card, food, water, health, info, bus, compass"

nodes, conns = [], {}
def node(name, type_, params, pos, version, **extra):
    n = {"parameters": params, "id": str(uuid.uuid4()), "name": name, "type": type_, "typeVersion": version, "position": pos}
    n.update(extra); nodes.append(n); return name
def link(a, b, out=0):
    conns.setdefault(a, {"main": []})
    while len(conns[a]["main"]) <= out: conns[a]["main"].append([])
    conns[a]["main"][out].append({"node": b, "type": "main", "index": 0})

# ---------------- code blocks ----------------
PLAN = r"""
// ===== SETTINGS: edit these =====
const S = {
  notifyEmail: 'noah@elevex.digital',
  renderUrl: 'http://tsw-video:8090',
  uploadUser: 'default',
  timelyWaitMinutes: 120,     // Before You Fly, alerts, Week Ahead: time to tap Stop
  evergreenWaitMinutes: 10,   // tips, Did You Know?, stories
  timeZone: 'Asia/Jerusalem',
};
// =================================
const format = $json.format;
const day = new Date().toLocaleDateString('en-GB', { weekday: 'short', timeZone: S.timeZone });
const MAIN = { Mon: 'BEFORE YOU FLY', Tue: 'TRAVEL SMART', Wed: 'GLAD WE CHECKED', Thu: 'BEFORE YOU FLY', Fri: 'TRAVEL SMART', Sat: 'GLAD WE CHECKED', Sun: 'THE WEEK AHEAD' };
const QUICK = { Mon: 'DID YOU KNOW?', Tue: 'TRAVEL ALERT', Wed: 'TRAVEL SMART', Thu: 'DID YOU KNOW?', Fri: 'TRAVEL ALERT', Sat: 'DID YOU KNOW?', Sun: 'TRAVEL SMART' };
const series = (format === 'main' ? MAIN : QUICK)[day];
const kind = ['BEFORE YOU FLY', 'THE WEEK AHEAD', 'TRAVEL ALERT'].includes(series) ? 'timely' : series === 'GLAD WE CHECKED' ? 'story' : 'evergreen';
return [{ json: { ...S, format, series, kind, day, date: new Date().toISOString().slice(0, 10) } }];
"""

PROMPT = r"""
const plan = $('Plan today').first().json;
const alerts = $input.all().map(i => i.json).filter(a => a && a.title).slice(0, 30).map(a => ({
  place: a.regions?.name || '', category: a.category, severity: a.severity, title: a.title, summary: (a.summary || '').slice(0, 400),
  authority: a.issuing_authority || '', url: a.primary_source_url || '', published: (a.published_at || '').slice(0, 10) }));
const recent = ($getWorkflowStaticData('global').recent || []).slice(-30);

const rules = `You write short vertical videos for Travel Safety Watch (TSW), a free app with official travel advice, weather and local news translated into plain English.
AUDIENCE: independent travellers aged 18-35 from the UK, US, Canada and Australia, many of them women travelling solo or as couples. Speak to one person, like a calm, well-travelled friend.
TODAY: ${plan.date}. FORMAT: ${plan.format} (${plan.format === 'main' ? '25-35 seconds' : '12-15 seconds'}). SERIES: ${plan.series}.

SERIES GUIDE
- BEFORE YOU FLY (main): one destination with something real happening in the alerts below (strike, storm, heat, protest, rule change). Hook "Going to X this week?". Say what is happening, where, when, and one practical thing to do. Name the source authority.
- THE WEEK AHEAD (main): three places from the alerts below to keep an eye on this week, one list scene plus a closing practical tip.
- TRAVEL ALERT (quick): one alert from the list below in one or two sentences, with the source.
- TRAVEL SMART (main or quick): a practical, evergreen habit, scam to know, or solo-safety tip. Useful anywhere, widely known to be true.
- DID YOU KNOW? (quick): a surprising, well-documented custom, rule or law travellers should know. Must be true today.
- GLAD WE CHECKED (main): a short fictional mini-story told with stock footage. A traveller, couple or family hits a moment where locals know something they don't (language barrier), and the TSW app explains it in plain English. Never use a real current event or a real named place with an invented event; keep places generic ("the station", "the old town"). If danger is involved, the people move to safety first and read the app on the way; the narration says "follow local authorities first".

FACTS (most important)
- For BEFORE YOU FLY, THE WEEK AHEAD and TRAVEL ALERT use ONLY the alerts provided. Never invent places, dates, numbers or events. Put the URL(s) you used in "sources" (copied exactly from the list).
- If no alert below is suitable for a calm, useful video, write a TRAVEL SMART video instead and set "series" to "TRAVEL SMART".
- For evergreen series use only well-established facts. No statistics unless they are widely documented. When unsure, give advice instead of facts.
- Never mention deaths, victims or attacks as the hook. Never use fear: no "don't go", "deadly", "nightmare", "shocking". No politics. No "download now".
- Do not write the app scene or the ending: they are added automatically.

OUTPUT: JSON only, with this shape:
{
 "series": "...", "format": "${plan.format}",
 "topic": "short-slug-of-the-topic",
 "title": "searchable YouTube title, max 80 characters, no emoji",
 "caption": "social caption, max 150 characters, then 3-5 hashtags",
 "sources": ["https://..."],
 "scenes": [ ...${plan.format === 'main' ? '3 to 4' : '2'} scenes... ]
}
Total spoken words across scenes: ${plan.format === 'main' ? '55-80' : '22-38'}.

SCENE TYPES (every scene has "type" and "say"; optional "caption")
- hook: {"type":"hook","headline":"max 40 chars","big":"optional short number or word shown huge, e.g. 3","icon":"optional icon","pill":{"text":"max 28 chars","icon":"...","at":"word"}}  Always the first scene.
- point: {"type":"point","n":"optional 1/2/3 for numbered tips","headline":"max 32 chars","icon":"optional","pills":[{"text":"max 30 chars","icon":"optional","style":"light|teal|coral|note","at":"word"}]}  max 2 pills.
- number: {"type":"number","label":"max 28 chars, capitals","value":"max 6 chars, e.g. 1992 or 112","at":"word","pills":[...]}
- place: {"type":"place","name":"place name","country":"country","level":"optional: avoid|reconsider|take_care|be_aware|clear (only if the alert says so)","level_at":"word","source":"Source: <authority> · as of <date>","pills":[...]}
- list: {"type":"list","headline":"max 32 chars","items":[{"name":"place","tag":"max 26 chars","level":"optional","at":"word"}]}  exactly 3 items.
- stock (GLAD WE CHECKED only): {"type":"stock","stock_query":"2-4 English words for a stock video search, e.g. train station crowd","headline":"optional max 40 chars","phone":{"title":"max 32 chars, what the app shows","text":"max 70 chars","at":"word"},"pills":[...]}
ICONS (use only these names): __ICONS__
- "say" is what the narrator speaks: write numbers as words when they could be misread ("nine one one", "nineteen ninety two"), and say web addresses as words.
- "caption" is the on-screen text of the same words in British spelling with digits ("911", "1992"). Leave it out when identical to "say".
- Every "at" must be ONE word that appears in that scene's caption (or say). It times the animation.
- Keep each scene to 1-3 short sentences.

AVOID REPEATING THESE RECENT TOPICS: ${recent.join(', ') || 'none yet'}

ALERTS FROM TSW (last 72 hours):
${alerts.length ? JSON.stringify(alerts) : 'none'}`;

return [{ json: { body: { contents: [{ role: 'user', parts: [{ text: rules }] }], generationConfig: { responseMimeType: 'application/json', temperature: 0.8 } }, alertUrls: alerts.map(a => a.url).filter(Boolean) } }];
"""

CHECK = r"""
const plan = $('Plan today').first().json;
const alertUrls = $('Write prompt').first().json.alertUrls || [];
const ICONS = new Set(`__ICONS__`.split(',').map(s => s.trim()));
const TYPES = new Set(['hook', 'point', 'number', 'place', 'list', 'stock']);
const problems = [];
let spec;
try {
  const txt = $json.candidates?.[0]?.content?.parts?.map(p => p.text).join('') || '';
  spec = JSON.parse(txt.replace(/^```json\s*|\s*```$/g, ''));
} catch (e) { return [{ json: { ok: false, problems: ['Gemini did not return valid JSON'], plan } }]; }

spec.format = plan.format;
const timely = ['BEFORE YOU FLY', 'THE WEEK AHEAD', 'TRAVEL ALERT'].includes(spec.series);
const story = spec.series === 'GLAD WE CHECKED';
if (!Array.isArray(spec.scenes) || spec.scenes.length < 2 || spec.scenes.length > 5) problems.push('wrong number of scenes');
const words = [];
for (const sc of spec.scenes || []) {
  if (!TYPES.has(sc.type)) problems.push(`unknown scene type ${sc.type}`);
  if (!sc.say || !String(sc.say).trim()) problems.push(`a ${sc.type} scene has nothing to say`);
  if (sc.type === 'stock' && !story) sc.type = 'point';
  if (sc.type === 'stock' && !sc.stock_query) problems.push('stock scene without stock_query');
  if (sc.icon && !ICONS.has(sc.icon)) delete sc.icon;
  if (sc.pill?.icon && !ICONS.has(sc.pill.icon)) delete sc.pill.icon;
  if (Array.isArray(sc.pills)) { sc.pills = sc.pills.slice(0, 2); sc.pills.forEach(p => { if (p.icon && !ICONS.has(p.icon)) delete p.icon; }); }
  const capWords = String(sc.caption || sc.say || '').toLowerCase().replace(/[^\w'\s]/g, ' ').split(/\s+/);
  const fixAt = o => { if (o && o.at && !capWords.includes(String(o.at).toLowerCase().replace(/[^\w']/g, ''))) delete o.at; };
  fixAt(sc); fixAt(sc.pill); fixAt(sc.phone); (sc.pills || []).forEach(fixAt); (sc.items || []).forEach(fixAt);
  if (sc.level && !['avoid', 'reconsider', 'take_care', 'be_aware', 'clear'].includes(sc.level)) delete sc.level;
  words.push(...String(sc.say || '').split(/\s+/).filter(Boolean));
}
const [lo, hi] = plan.format === 'main' ? [40, 95] : [16, 45];
if (words.length < lo || words.length > hi) problems.push(`spoken length ${words.length} words (want ${lo}-${hi})`);
const all = JSON.stringify(spec).toLowerCase();
const banned = ["don't go", 'deadly', 'terrifying', 'horrifying', 'nightmare', 'shocking', 'download now', 'massacre', 'killed', 'slaughter'];
for (const b of banned) if (all.includes(b)) problems.push(`uses the word "${b}"`);
if (timely) {
  const srcs = (spec.sources || []).filter(u => alertUrls.includes(u));
  if (!srcs.length) problems.push('timely video without a source from the TSW alerts');
}
if (!spec.title || spec.title.length > 100) problems.push('missing or long title');
spec.title = String(spec.title || '').slice(0, 100);
spec.caption = String(spec.caption || '').slice(0, 300);
return [{ json: { ok: problems.length === 0, problems, plan, timely, story, spec: { format: spec.format, series: spec.series, cta: 'auto', scenes: spec.scenes }, meta: { title: spec.title, caption: spec.caption, sources: spec.sources || [], topic: spec.topic || spec.title } } }];
""".replace("__ICONS__", ICONS)

STOCKQ = r"""
const d = $('Check script').first().json;
return d.spec.scenes.map((sc, i) => ({ i, sc })).filter(x => x.sc.type === 'stock').map(x => ({ json: { i: x.i, q: x.sc.stock_query } }));
"""

ATTACH = r"""
const d = JSON.parse(JSON.stringify($('Check script').first().json));
const qs = $('Stock queries').all().map(x => x.json);
$input.all().forEach((res, k) => {
  const hits = res.json.hits || [];
  const pick = hits.find(h => h.videos?.medium?.url) || hits[0];
  const url = pick?.videos?.medium?.url || pick?.videos?.small?.url;
  const target = qs[k];
  if (target && url) d.spec.scenes[target.i].clip_url = url;
});
return [{ json: d }];
"""

PREVIEW_HTML = r"""={{ (() => { const d = $('Render video').item.json; const c = $('Check script').first().json; const mins = c.timely ? c.plan.timelyWaitMinutes : c.plan.evergreenWaitMinutes; const at = new Date(Date.now() + mins * 60000).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: c.plan.timeZone }); const stop = $execution.resumeUrl + '?action=stop', now = $execution.resumeUrl + '?action=post'; return `<p><b>${c.spec.series}</b> · ${c.plan.format} · ${d.duration}s</p><p><b>${c.meta.title}</b><br>${c.meta.caption}</p><p>Sources: ${(c.meta.sources || []).join(' ') || 'none (evergreen tip)'}</p><p>The video is attached. It posts automatically at <b>${at}</b> unless you click Stop.</p><p><a href="${stop}" style="background:#E05A47;color:#fff;padding:12px 20px;border-radius:8px;text-decoration:none;font-weight:bold">Stop: don't post</a> &nbsp; <a href="${now}" style="background:#1F7A8C;color:#fff;padding:12px 20px;border-radius:8px;text-decoration:none;font-weight:bold">Post now</a></p>`; })() }}"""

RESTORE = r"""
const v = $('Download video').first();
const c = $('Check script').first().json;
return [{ json: c, binary: v.binary }];
"""

REMEMBER = r"""
const s = $getWorkflowStaticData('global');
const c = $('Check script').first().json;
s.recent = [...(s.recent || []), c.meta.topic].slice(-60);
return [{ json: { posted: true, topic: c.meta.topic, result: $json } }];
"""

# ---------------- nodes ----------------
node("Main video 19:00", "n8n-nodes-base.scheduleTrigger", {"rule": {"interval": [{"field": "cronExpression", "expression": "0 19 * * *"}]}}, [0, 0], 1.2)
node("Quick video 13:00", "n8n-nodes-base.scheduleTrigger", {"rule": {"interval": [{"field": "cronExpression", "expression": "0 13 * * *"}]}}, [0, 220], 1.2)
def setfmt(name, fmt, pos):
    return node(name, "n8n-nodes-base.set", {"assignments": {"assignments": [{"id": str(uuid.uuid4()), "name": "format", "value": fmt, "type": "string"}]}, "options": {}}, pos, 3.4)
setfmt("Main", "main", [220, 0]); setfmt("Quick", "quick", [220, 220])
node("Plan today", "n8n-nodes-base.code", {"jsCode": PLAN}, [440, 110], 2)
node("TSW alerts (72h)", "n8n-nodes-base.httpRequest", {
    "url": f"={SUPA}/rest/v1/alerts",
    "sendQuery": True, "queryParameters": {"parameters": [
        {"name": "select", "value": "title,summary,category,severity,issuing_authority,primary_source_url,published_at,regions:regions!alerts_region_id_fkey(name,slug)"},
        {"name": "status", "value": "eq.published"},
        {"name": "published_at", "value": "={{ 'gte.' + new Date(Date.now() - 72*3600*1000).toISOString() }}"},
        {"name": "order", "value": "published_at.desc"},
        {"name": "limit", "value": "40"}]},
    "sendHeaders": True, "headerParameters": {"parameters": [{"name": "apikey", "value": ANON}]},
    "options": {}}, [660, 110], 4.2, alwaysOutputData=True)
node("Write prompt", "n8n-nodes-base.code", {"jsCode": PROMPT.replace("__ICONS__", ICONS)}, [880, 110], 2)
node("Gemini: write script", "n8n-nodes-base.httpRequest", {
    "method": "POST", "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
    "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
    "sendBody": True, "specifyBody": "json", "jsonBody": "={{ JSON.stringify($json.body) }}",
    "options": {"timeout": 120000}}, [1100, 110], 4.2, retryOnFail=True, maxTries=5, waitBetweenTries=10000)
node("Check script", "n8n-nodes-base.code", {"jsCode": CHECK}, [1320, 110], 2)
def ifnode(name, expr, pos):
    return node(name, "n8n-nodes-base.if", {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
        "conditions": [{"id": str(uuid.uuid4()), "leftValue": expr, "rightValue": "", "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
        "combinator": "and"}, "options": {}}, pos, 2.2)
ifnode("Script OK?", "={{ $json.ok }}", [1540, 110])
def mail(name, subject, message, pos, attach=False):
    opts = {"appendAttribution": False}
    if attach: opts["attachmentsUi"] = {"attachmentsBinary": [{"property": "data"}]}
    return node(name, "n8n-nodes-base.gmail", {"sendTo": "={{ $('Plan today').first().json.notifyEmail }}", "subject": subject,
        "emailType": "html", "message": message, "options": opts}, pos, 2.1)
mail("Email: needs you", "={{ 'TSW video held back: ' + $json.plan.series }}",
    "={{ `<p>A TSW video (${$json.plan.series}, ${$json.plan.format}) was held back. Nothing was posted.</p><p>Problems:</p><ul>${$json.problems.map(p => '<li>' + p + '</li>').join('')}</ul><p>It will try again at the next scheduled time.</p>` }}", [1760, 300])
ifnode("Story with clips?", "={{ $json.story && $json.spec.scenes.some(s => s.type === 'stock') }}", [1760, 0])
node("Stock queries", "n8n-nodes-base.code", {"jsCode": STOCKQ}, [1980, -120], 2)
node("Pixabay search", "n8n-nodes-base.httpRequest", {
    "url": "https://pixabay.com/api/videos/", "authentication": "genericCredentialType", "genericAuthType": "httpQueryAuth",
    "sendQuery": True, "queryParameters": {"parameters": [{"name": "q", "value": "={{ $json.q }}"}, {"name": "video_type", "value": "film"},
        {"name": "safesearch", "value": "true"}, {"name": "per_page", "value": "5"}, {"name": "order", "value": "popular"}]},
    "options": {}}, [2200, -120], 4.2, alwaysOutputData=True)
node("Attach clips", "n8n-nodes-base.code", {"jsCode": ATTACH}, [2420, -120], 2)
node("Render video", "n8n-nodes-base.httpRequest", {
    "method": "POST", "url": "={{ $('Plan today').first().json.renderUrl }}/render",
    "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
    "sendBody": True, "specifyBody": "json", "jsonBody": "={{ JSON.stringify($json.spec) }}",
    "options": {"timeout": 900000}}, [2640, 0], 4.2, onError="continueErrorOutput")
node("Download video", "n8n-nodes-base.httpRequest", {
    "url": "={{ $('Plan today').first().json.renderUrl + $json.file }}",
    "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
    "options": {"response": {"response": {"responseFormat": "file", "outputPropertyName": "data"}}}}, [2860, 0], 4.2)
mail("Email: preview", "={{ 'TSW video ready: ' + $('Check script').first().json.meta.title }}", PREVIEW_HTML, [3080, 0], attach=True)
node("Window to stop", "n8n-nodes-base.wait", {
    "resume": "webhook", "httpMethod": "GET", "limitWaitTime": True, "limitType": "afterTimeInterval",
    "resumeAmount": "={{ $('Check script').first().json.timely ? $('Plan today').first().json.timelyWaitMinutes : $('Plan today').first().json.evergreenWaitMinutes }}",
    "resumeUnit": "minutes", "options": {}}, [3300, 0], 1.1, webhookId=str(uuid.uuid4()))
ifnode("Stopped?", "={{ $json.query?.action === 'stop' }}", [3520, 0])
mail("Email: cancelled", "TSW video stopped", "<p>Stopped. That video was not posted.</p>", [3740, -120])
node("Restore video", "n8n-nodes-base.code", {"jsCode": RESTORE}, [3740, 100], 2)
upload_params = [{"name": "user", "value": "={{ $json.plan.uploadUser }}"},
    {"parameterType": "formBinaryData", "name": "video", "inputDataFieldName": "data"},
    {"name": "title", "value": "={{ $json.meta.title }}"},
    {"name": "youtube_title", "value": "={{ $json.meta.title }}"},
    {"name": "youtube_description", "value": "={{ $json.meta.caption + '\\n\\nFree travel safety alerts: https://travelsafetywatch.com' + (($json.meta.sources||[]).length ? '\\nSource: ' + $json.meta.sources.join(' ') : '') }}"},
    {"name": "instagram_title", "value": "={{ $json.meta.caption }}"},
    {"name": "facebook_title", "value": "={{ $json.meta.caption }}"},
    {"name": "tiktok_title", "value": "={{ $json.meta.caption }}"}]
for p in ["youtube", "instagram", "facebook"]:   # to add TikTok later: duplicate one of these rows in n8n and set it to tiktok
    upload_params.append({"name": "platform[]", "value": p})
node("Post to socials", "n8n-nodes-base.httpRequest", {
    "method": "POST", "url": "https://api.upload-post.com/api/upload",
    "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
    "sendBody": True, "contentType": "multipart-form-data", "bodyParameters": {"parameters": upload_params},
    "options": {"timeout": 600000}}, [3960, 100], 4.2, onError="continueErrorOutput")
node("Remember topic", "n8n-nodes-base.code", {"jsCode": REMEMBER}, [4180, 0], 2)
mail("Email: posted", "={{ 'TSW video posted: ' + $('Check script').first().json.meta.title }}", "={{ '<p>Posted to ' + $('Plan today').first().json.uploadUser + ' accounts: ' + $('Check script').first().json.meta.title + '</p>' }}", [4400, 0])
mail("Email: problem", "TSW video problem: nothing posted", "={{ '<p>Something went wrong, nothing was posted.</p><pre>' + JSON.stringify($json.error || $json).slice(0, 800) + '</pre>' }}", [3080, 320])

link("Main video 19:00", "Main"); link("Quick video 13:00", "Quick")
link("Main", "Plan today"); link("Quick", "Plan today")
link("Plan today", "TSW alerts (72h)"); link("TSW alerts (72h)", "Write prompt"); link("Write prompt", "Gemini: write script")
link("Gemini: write script", "Check script"); link("Check script", "Script OK?")
link("Script OK?", "Story with clips?", 0); link("Script OK?", "Email: needs you", 1)
link("Story with clips?", "Stock queries", 0); link("Story with clips?", "Render video", 1)
link("Stock queries", "Pixabay search"); link("Pixabay search", "Attach clips"); link("Attach clips", "Render video")
link("Render video", "Download video", 0); link("Render video", "Email: problem", 1)
link("Download video", "Email: preview"); link("Email: preview", "Window to stop"); link("Window to stop", "Stopped?")
link("Stopped?", "Email: cancelled", 0); link("Stopped?", "Restore video", 1)
link("Restore video", "Post to socials"); link("Post to socials", "Remember topic", 0); link("Post to socials", "Email: problem", 1)
link("Remember topic", "Email: posted")

wf = {"name": "TSW: daily videos", "nodes": nodes, "connections": conns, "active": False,
      "settings": {"executionOrder": "v1", "timezone": "Asia/Jerusalem", "saveDataSuccessExecution": "all"}, "pinData": {}}
out = HERE / "TSW_Daily_Videos.json"
out.write_text(json.dumps(wf, indent=1, ensure_ascii=False))
print("wrote", out, len(nodes), "nodes")

const $=id=>document.getElementById(id);
const state={
 original:null,current:null,originalFile:null,running:false,generation:0,prompt:"",
 description:"",stable:0,history:[],candidates:[],parentId:null,
 bestScore:0,scoreHistory:[],plateau:false
};

function log(msg,cls=""){const d=document.createElement("div");d.className="logline "+cls;d.textContent=`[${new Date().toLocaleTimeString()}] ${msg}`;$("log").appendChild(d);$("log").scrollTop=$("log").scrollHeight;}
function setStatus(t){$("health").textContent=t}
function blobToDataURL(blob){return new Promise((res,rej)=>{const r=new FileReader();r.onload=()=>res(r.result);r.onerror=rej;r.readAsDataURL(blob)})}
function dataURLToBlob(url){return fetch(url).then(r=>r.blob())}
function drawURL(canvas,url){return new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>{const c=canvas.getContext("2d");c.clearRect(0,0,canvas.width,canvas.height);const s=Math.min(canvas.width/img.width,canvas.height/img.height),w=img.width*s,h=img.height*s;c.drawImage(img,(canvas.width-w)/2,(canvas.height-h)/2,w,h);resolve(img)};img.onerror=reject;img.src=url})}
function extractText(resp){return resp?.message?.content || resp?.content || resp?.text || String(resp||"")}

async function health(){
 try{const r=await fetch("/api/health");const j=await r.json();setStatus(`local metrics ✓ | Ollama ${j.ollama?"✓ "+j.ollama_model:"–"}`)}
 catch(e){setStatus("local backend ✗")}
}
health();

$("signin").onclick=async()=>{try{await puter.auth.signIn();log("Puter-Anmeldung erfolgreich.","good")}catch(e){log("Puter-Anmeldung: "+e,"bad")}};

$("file").onchange=async e=>{
 const f=e.target.files[0];if(!f)return;
 state.originalFile=f;state.original=f;state.current=f;state.generation=0;state.stable=0;state.history=[];state.prompt="";
 await drawURL($("orig"),URL.createObjectURL(f));await drawURL($("current"),URL.createObjectURL(f));
 log(`Initialbild geladen: ${f.name} (${f.size} bytes)`,"good");
};

async function puterImageURL(blob, name){
 const path=`infinity-reconstruction/${Date.now()}_${name}`;
 await puter.fs.write(path,blob,{createMissingParents:true,overwrite:true});
 return await puter.fs.getReadURL(path,"2h");
}

const ANALYSIS_INSTRUCTION=`You are the visual measurement stage of an experimental image-reconstruction loop.
Analyze the supplied image for the purpose of reconstructing it from words alone.
Return a highly detailed, factual, structured description. Do NOT beautify, interpret, or invent.
Cover:
1. canvas aspect ratio and framing;
2. camera/viewpoint, perspective and apparent focal characteristics;
3. global composition;
4. every visible object/subject and its normalized position (x,y), relative width/height and orientation;
5. spatial relationships and overlaps;
6. foreground/midground/background and depth ordering;
7. dominant and secondary colors with approximate roles;
8. lighting direction, intensity, color temperature and shadows;
9. materials, surface properties and textures;
10. distinctive small details;
11. typography/signage if present;
12. uncertainty: explicitly mark anything not reliably observable.
Write the result as a reconstruction specification, not as poetic prose.`;

async function analyzePuter(blob){
 const url=await puterImageURL(blob,"analysis.png");
 log("Puter Vision: Bild wird analysiert …");
 const r=await puter.ai.chat(ANALYSIS_INSTRUCTION,url,{model:$("visionModel").value});
 const text=extractText(r);
 if(!text)throw new Error("Puter Vision lieferte keinen Beschreibungstext.");
 return text;
}
async function analyzeOllama(blob){
 const fd=new FormData();fd.append("file",blob,"frame.png");fd.append("instruction",ANALYSIS_INSTRUCTION);
 const r=await fetch("/api/ollama/analyze",{method:"POST",body:fd});
 if(!r.ok)throw new Error(await r.text());
 return (await r.json()).text;
}
async function analyze(blob){
 const t=$("analyzer").value==="ollama"?await analyzeOllama(blob):await analyzePuter(blob);
 state.description=t;$("desc").textContent=t;log("Beschreibung erhalten ("+t.length+" Zeichen).","good");
 return t;
}

const ADAPTER_SYSTEM=`You are the prompt adapter in a visual reconstruction experiment.
Transform the supplied observation into a generator prompt whose only goal is maximum visual similarity to the reference.
Preserve facts. Increase precision where geometry, relative position, scale, color, depth, lighting and distinctive details matter.
Do not add cinematic beauty, style, objects, moods, or details that are not supported by the observation.
Return ONLY the final image-generation prompt.`;

async function makePrompt(description, previous, feedback=""){
 const text=`${ADAPTER_SYSTEM}

OBSERVATION:
${description}

PREVIOUS PROMPT:
${previous||"(none)"}

FEEDBACK FROM COMPARISON:
${feedback||"(none)"}

Construct the most explicit faithful reconstruction prompt possible.`;
 const r=await puter.ai.chat(text,{model:$("visionModel").value});
 return extractText(r).trim();
}
async function mutatePrompt(prompt,description,direction){
 const instruction=`You are optimizing a visual reconstruction prompt.
Reference observation:
${description}

Current prompt:
${prompt}

Optimization direction: ${direction}
Return ONLY one complete replacement prompt. Preserve everything that already matches. Change only what can plausibly improve fidelity.`;
 const r=await puter.ai.chat(instruction,{model:$("visionModel").value});
 return extractText(r).trim();
}

async function generate(prompt){
 log(`Generator: ${$("genModel").value} …`);
 const img=await puter.ai.txt2img(prompt,{model:$("genModel").value});
 if(!img)throw new Error("Generator lieferte kein Bild.");
 const src=img.src||img.getAttribute("src");
 if(!src)throw new Error("Generator-Bild hat keine Quelle.");
 const r=await fetch(src);if(!r.ok)throw new Error("Generiertes Bild konnte nicht geladen werden.");
 return await r.blob();
}

async function compare(blob,reference=state.originalFile){
 const fd=new FormData();fd.append("reference",reference,"reference.png");fd.append("candidate",blob,"candidate.png");
 const r=await fetch("/api/compare",{method:"POST",body:fd});if(!r.ok)throw new Error(await r.text());return await r.json();
}
function metricHTML(m){
 if(!m)return "<span>—</span><b>kein Vergleich</b>";
 return Object.entries({
 "Composite":(m.composite*100).toFixed(2)+" %",
 "SSIM":(m.ssim*100).toFixed(2)+" %",
 "Edge IoU":(m.edge_iou*100).toFixed(2)+" %",
 "Color":(m.color_similarity*100).toFixed(2)+" %",
 "Gradient":(m.gradient_similarity*100).toFixed(2)+" %",
 "Thumbnail":(m.thumbnail_similarity*100).toFixed(2)+" %",
 "PSNR":m.psnr_db.toFixed(2)+" dB",
 "MSE":m.mse.toFixed(2)
 }).map(([k,v])=>`<span>${k}</span><b>${v}</b>`).join("");
}
function showMetrics(m,previous){
 $("metrics").innerHTML=metricHTML(m);
 $("previousMetrics").innerHTML=metricHTML(previous);
}

function renderCandidates(){
 const c=$("candidates");c.innerHTML="";
 state.candidates.forEach((x,i)=>{
	const d=document.createElement("div");d.className="candidate"+(x.selected?" selected":"");
	const im=document.createElement("img");im.src=x.url;d.appendChild(im);
	const s=document.createElement("div");s.className="score";s.textContent=`${x.label} | ${(x.metrics.composite*100).toFixed(2)}% | SSIM ${(x.metrics.ssim*100).toFixed(1)}%`;
	d.appendChild(s);d.onclick=()=>{state.candidates.forEach(y=>y.selected=false);x.selected=true;renderCandidates();log(`Menschliche Auswahl: ${x.label}`,"good")};c.appendChild(d);
 });
}

async function archiveCandidate(x){
 const fd=new FormData();fd.append("image",x.blob,"image.png");
 fd.append("metadata",JSON.stringify({
 generation:state.generation,label:x.label,parent_id:state.parentId,
 prompt:x.prompt,description:state.description,metrics:x.metrics,
 previous_match:x.previousMetrics?.composite||0,human_selected:!!x.selected
 }));
 const r=await fetch("/api/archive",{method:"POST",body:fd});if(!r.ok)throw new Error(await r.text());const j=await r.json();
 $("archive").innerHTML+=`<div>G${state.generation} ${x.label}: ${j.run_id}</div>`;
}

async function runRound(){
 const g=state.generation;
 log(`===== GENERATION ${g} =====`);
 const desc=await analyze(state.current);
 if(!state.prompt){
	 state.prompt=await makePrompt(desc,"");
	 $("prompt").value=state.prompt;
	 log("Initialer Prompt-Adapter fertig.","good");
 } else log("Bester Prompt wird als Ausgangspunkt verwendet.");

 const n=Math.min(2,Math.max(1,Number($("variants").value)));
 const directions=[
	"conservative: improve measurable spatial geometry, normalized positions, scale and depth ordering; preserve all established facts",
	"exploratory: improve camera/viewpoint, perspective, lighting and explicit visual relationships; preserve all established facts"
 ];
 state.candidates=[];
 for(let i=0;i<n;i++){
	 const p=await mutatePrompt(state.prompt,desc,directions[i]);
	 log(`Variante ${i+1}: ${p.slice(0,260)}${p.length>260?"…":""}`);
	 const blob=await generate(p);
	 const url=URL.createObjectURL(blob);
	 const metrics=await compare(blob,state.originalFile);
	 const previousMetrics=state.current!==state.originalFile ? await compare(blob,state.current) : null;
	 state.candidates.push({
		 label:String.fromCharCode(65+i),blob,url,prompt:p,metrics,previousMetrics,selected:false
	 });
	 log(`Variante ${String.fromCharCode(65+i)} Original ${(metrics.composite*100).toFixed(2)}% | vorher ${(previousMetrics?previousMetrics.composite*100:0).toFixed(2)}%`);
	 await archiveCandidate(state.candidates.at(-1));
 }
 renderCandidates();

 let winner;
 if($("mode").value==="human"||$("mode").value==="both"){
	 const options=state.candidates.map(x=>`${x.label} = ${(x.metrics.composite*100).toFixed(2)}%`).join(" | ");
	 const choice=prompt(
		 `Generation ${g}: Welche Variante ist dem ORIGINAL am ähnlichsten?\n${options}\n\nA = Variante A\nB = Variante B\nE = gleich / unentschieden`,
		 "A"
	 );
	 if((choice||"A").toUpperCase()==="E"){
		 winner=[...state.candidates].sort((a,b)=>b.metrics.composite-a.metrics.composite)[0];
		 log("Human: Unentschieden; automatische Auswahl des höheren Scores als Tie-Breaker.","warn");
	 }else{
		 const idx=(choice||"A").toUpperCase()==="B"?1:0;
		 winner=state.candidates[Math.min(idx,state.candidates.length-1)];
		 log(`Menschliches Urteil: ${winner.label}`,"good");
	 }
 } else {
	 winner=[...state.candidates].sort((a,b)=>b.metrics.composite-a.metrics.composite)[0];
	 log(`Automatische Auswahl: ${winner.label}`,"good");
 }
 state.candidates.forEach(x=>x.selected=x===winner);
 renderCandidates();

 const previousMatch=winner.previousMetrics;
 showMetrics(winner.metrics,previousMatch);
 state.current=winner.blob;
 state.prompt=winner.prompt;
 state.parentId=await archiveWinnerLineage(winner);
 $("prompt").value=winner.prompt;
 await drawURL($("current"),winner.url);

 state.scoreHistory.push(winner.metrics.composite);
 state.bestScore=Math.max(state.bestScore,winner.metrics.composite);
 const threshold=Number($("threshold").value);
 state.stable=winner.metrics.composite>=threshold?state.stable+1:0;

 const plateauN=Number($("plateauN").value);
 const delta=Number($("plateauDelta").value);
 if(state.scoreHistory.length>=plateauN){
	 const recent=state.scoreHistory.slice(-plateauN);
	 const improvement=Math.max(...recent)-Math.min(...recent);
	 state.plateau=improvement<delta;
 } else state.plateau=false;

 $("convergence").textContent=
	 `G${g} | aktueller ${(winner.metrics.composite*100).toFixed(2)}% | Best ${(state.bestScore*100).toFixed(2)}% | `
	 +`≥Schwelle ${state.stable}/${$("stableN").value} | Plateau ${state.plateau?"JA":"nein"}`;

 log(`Original-Match ${(winner.metrics.composite*100).toFixed(2)}%; Vorher ${(previousMatch?previousMatch.composite*100:0).toFixed(2)}%; Best ${(state.bestScore*100).toFixed(2)}%.`);

 if(state.stable>=Number($("stableN").value)){
	 log("Abbruch: Schwelle über mehrere Generationen stabil erreicht.","good");state.running=false;return;
 }
 if(state.plateau && state.scoreHistory.length>=plateauN){
	 log("Abbruch: messbares Plateau erreicht.","warn");state.running=false;return;
 }
 state.generation++;
 if(state.generation>=Number($("maxGen").value)){
	 log("Abbruch: maximale Generationenzahl erreicht.","warn");state.running=false;return;
 }
}

async function archiveWinnerLineage(x){
 const fd=new FormData();fd.append("image",x.blob,"winner.png");
 fd.append("metadata",JSON.stringify({
	 generation:state.generation,label:`WINNER_${x.label}`,parent_id:state.parentId,
	 prompt:x.prompt,description:state.description,metrics:x.metrics,
	 previous_match:x.previousMetrics?.composite||0,human_selected:!!x.selected
 }));
 const r=await fetch("/api/archive",{method:"POST",body:fd});
 if(!r.ok)throw new Error(await r.text());
 const j=await r.json();
 $("archive").innerHTML+=`<div>G${state.generation} WINNER ${x.label}: ${j.run_id}</div>`;
 state.history.push({id:j.run_id,prompt:x.prompt,score:x.metrics.composite});
 return j.run_id;
}
async function loop(){
 while(state.running){
	try{await runRound()}catch(e){log("FEHLER: "+(e?.message||e),"bad");state.running=false}
	if(state.running)await new Promise(r=>setTimeout(r,200));
 }
}

$("start").onclick=async()=>{
 if(!state.originalFile){alert("Bitte zuerst ein Initialbild laden.");return}
 state.running=true;$("start").disabled=true;$("stop").disabled=false;
 log("Loop gestartet.","good");await loop();$("start").disabled=false;
};
$("stop").onclick=()=>{state.running=false;log("Loop gestoppt.","warn")};
$("analyzeNow").onclick=async()=>{
 if(!state.current){alert("Bild laden.");return}
 try{const d=await analyze(state.current);state.prompt=await makePrompt(d,state.prompt);$("prompt").value=state.prompt;log("Analyse + Prompt manuell aktualisiert.","good")}catch(e){log("FEHLER: "+e.message,"bad")}
};
$("meta").onclick=async()=>{
 try{
	 const r=await fetch("/api/history?limit=50");
	 const rows=await r.json();
	 const winners=rows.filter(x=>x.human_selected||String(x.label||"").startsWith("WINNER")).reverse().slice(-30);
	 if(!winners.length && !state.prompt){log("Noch keine erfolgreichen Promptlinien vorhanden.","warn");return;}
	 const material=(winners.length?winners:state.history).map((x,i)=>
		 `PROMPT ${i+1}:\n${x.prompt}\nSCORE:${x.original_match??x.score}`).join("\n\n");
	 const r2=await puter.ai.chat(`You are the meta-analysis engine of a visual reconstruction experiment.
Extract only evidence-based, recurring prompt structures from the successful candidates below.
Distinguish stable patterns from one-off wording.
Produce a reusable MASTER PROMPT TEMPLATE with explicit sections:
SCENE, CAMERA, COMPOSITION, OBJECTS, NORMALIZED POSITION, RELATIVE SCALE,
SPATIAL RELATIONS, DEPTH, GEOMETRY, COLOR, LIGHT, MATERIAL, TEXTURE,
BACKGROUND, MICRO-DETAILS, UNCERTAINTY.
The template must optimize faithful reconstruction, not aesthetic enhancement.
Do not claim universal validity without evidence.

EXPERIMENTS:
${material}`,{model:$("visionModel").value});
	 const t=extractText(r2);
	 state.prompt=t;$("prompt").value=t;
	 await fetch("/api/archive/meta",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body:"metadata="+encodeURIComponent(JSON.stringify({content:t,source_count:winners.length}))});
	 log(`MetaMaster archiviert aus ${winners.length} erfolgreichen Experimenten.`,"good");
 }catch(e){log("MetaMaster Fehler: "+e.message,"bad")}
};
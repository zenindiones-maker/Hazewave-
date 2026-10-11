// HAZEWAVE Note Studio. No frameworks, network or external dependencies.
// All operations remain client-side; file uploads never occur.
export const PPQ = 480;
export const ROW = 19;
export const LOW = 36;
export const HIGH = 95;

export function normalizeNote(note) {
  const pitch = Number(note.midi_note);
  const start = Number(note.start_seconds);
  const end = Number(note.end_seconds);
  const velocity = Number(note.velocity ?? 90);
  if (!Number.isInteger(pitch) || pitch < 0 || pitch > 127 ||
      !Number.isFinite(start) || !Number.isFinite(end) ||
      start < 0 || end <= start || end > 3600 ||
      !Number.isFinite(velocity) || velocity < 1 || velocity > 127) {
    throw new Error("INVALID_NOTE_DATA");
  }
  return {midi_note:pitch, start_seconds:start, end_seconds:end,
          velocity:Math.round(velocity)};
}

export function parseNoteMap(value) {
  const data = typeof value === "string" ? JSON.parse(value) : value;
  const map = data?.result || data;
  if (!map || !Array.isArray(map.notes) || map.notes.length > 40000)
    throw new Error("INVALID_HAZEWAVE_NOTE_MAP");
  return {
    source: map.source || null,
    notes: map.notes.map(normalizeNote),
    engine: map.engine || map.method || "imported",
  };
}

export function quantizeNotes(notes, bpm, subdivisions=4) {
  if (!(bpm >= 30 && bpm <= 300) || ![1,2,4,8,16].includes(subdivisions))
    throw new Error("INVALID_GRID");
  const step = 60 / bpm / subdivisions;
  const quantize = (x) => Math.round(x / step) * step;
  return notes.map(n => {
    const a = quantize(n.start_seconds);
    const b = Math.max(a+step, quantize(n.end_seconds));
    return normalizeNote({...n, start_seconds:+a.toFixed(6), end_seconds:+b.toFixed(6)});
  });
}

export function vlq(value) {
  if (!Number.isInteger(value) || value < 0 || value > 0x0fffffff)
    throw new Error("INVALID_MIDI_DELTA");
  const bytes=[value & 127];
  for (value >>= 7; value; value >>= 7) bytes.unshift((value & 127) | 128);
  return bytes;
}

export function encodeMidi(notes, bpm=120) {
  if (!Number.isInteger(bpm) || bpm < 30 || bpm > 300)
    throw new Error("INVALID_BPM");
  const tempo=Math.round(60000000/bpm);
  const sorted=[];
  for(const raw of notes) {
    const n=normalizeNote(raw);
    const time=s => Math.round(s*bpm*PPQ/60);
    const begin=time(n.start_seconds), end=Math.max(begin+1,time(n.end_seconds));
    sorted.push({tick:begin,priority:1,data:[0x90,n.midi_note,n.velocity]});
    sorted.push({tick:end,priority:0,data:[0x80,n.midi_note,0]});
  }
  sorted.sort((a,b)=>a.tick-b.tick||a.priority-b.priority||a.data[1]-b.data[1]);
  const track=[0,0xff,0x51,3,(tempo>>16)&255,(tempo>>8)&255,tempo&255];
  let previous=0;
  for(const event of sorted){
    track.push(...vlq(event.tick-previous),...event.data);
    previous=event.tick;
  }
  track.push(0,0xff,0x2f,0);
  const n=track.length;
  return new Uint8Array([
    77,84,104,100,0,0,0,6,0,0,0,1,PPQ>>8,PPQ&255,
    77,84,114,107,(n>>>24)&255,(n>>>16)&255,(n>>>8)&255,n&255,
    ...track
  ]);
}

export function noteName(pitch) {
  const keys=["C","C♯","D","D♯","E","F","F♯","G","G♯","A","A♯","B"];
  return keys[pitch%12]+(Math.floor(pitch/12)-1);
}

const $=id=>document.getElementById(id);
const clone=items=>items.map(n=>({...n}));
function launch() {
  if(!document.getElementById("note-grid")) return;
  let notes=[],source=null,engine="—",history=[],future=[],selected=-1;
  let bpm=120,zoom=110,audioUrl=null,ac=null,playTimers=[];
  const grid=$("note-grid"),labels=$("piano-keys"),footer=$("status");
  const historyPush=()=>{history.push(clone(notes));if(history.length>100)history.shift();future=[];};
  const say=message=>{footer.textContent=message;};
  const snapSeconds=t=>Math.max(0,Math.round(t/(60/bpm/4))*(60/bpm/4));
  const sec=x=>(x/zoom);
  const px=t=>(t*zoom);
  const yToPitch=y=>HIGH-Math.floor(y/ROW);
  const xToTime=x=>Math.max(0,snapSeconds(sec(x)));
  function updateStats() {
    $("note-count").textContent=String(notes.length);
    $("duration").textContent=(notes.reduce((m,n)=>Math.max(m,n.end_seconds),0)).toFixed(2)+"s";
    $("engine").textContent=engine;
    $("bpm").value=String(bpm);
  }
  function draw() {
    grid.replaceChildren();
    labels.replaceChildren();
    grid.style.width="max(1200px,"+Math.ceil(Math.max(12,
      notes.reduce((m,n)=>Math.max(m,n.end_seconds),0)+3)*zoom)+"px)";
    grid.style.height=(HIGH-LOW+1)*ROW+"px";
    grid.style.backgroundSize= (zoom/4)+"px "+ROW+"px";
    for(let pitch=HIGH;pitch>=LOW;pitch--){
      const key=document.createElement("div");
      key.className="key"+([1,3,6,8,10].includes(pitch%12)?" black":"")+(pitch%12===0?" octave":"");
      key.style.height=ROW+"px";
      key.textContent=pitch%12===0?noteName(pitch):"";
      labels.append(key);
    }
    notes.forEach((note,index)=>{
      if(note.midi_note<LOW||note.midi_note>HIGH)return;
      const element=document.createElement("div");
      element.className="note"+(index===selected?" selected":"");
      element.dataset.index=String(index);
      element.setAttribute("role","button");
      element.tabIndex=0;
      element.setAttribute("aria-label",noteName(note.midi_note)+" "+note.start_seconds+" seconds");
      element.style.left=px(note.start_seconds)+"px";
      element.style.top=((HIGH-note.midi_note)*ROW+2)+"px";
      element.style.width=Math.max(6,px(note.end_seconds-note.start_seconds))+"px";
      element.style.height=(ROW-3)+"px";
      element.title=noteName(note.midi_note)+" • "+note.start_seconds.toFixed(2)+"s";
      element.textContent=noteName(note.midi_note);
      grid.append(element);
    });
    updateStats();
  }
  function selectionChange(i){
    selected=i;draw();
    const n=notes[i];
    $("selected").textContent=n?(noteName(n.midi_note)+" • "+n.start_seconds.toFixed(2)+"s–"+n.end_seconds.toFixed(2)+"s"):"Selecione uma nota";
  }
  function exportFile(bytes,name,mime){
    const url=URL.createObjectURL(new Blob([bytes],{type:mime}));
    const a=document.createElement("a");a.href=url;a.download=name;
    document.body.append(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),15000);
  }
  async function ingest(file) {
    if(file.size>12*1024*1024)throw new Error("Arquivo superior a 12 MiB");
    if(file.name.toLowerCase().endsWith(".wav")){
      if(audioUrl)URL.revokeObjectURL(audioUrl);
      audioUrl=URL.createObjectURL(file);
      $("audio").src=audioUrl;
      say("WAV carregado localmente. Importe o JSON gerado pelo Harness para ver notas.");
      return;
    }
    const map=parseNoteMap(await file.text());
    if(map.notes.length>2000)throw new Error("Limite do editor: 2.000 eventos");
    historyPush(); notes=map.notes;source=map.source;engine=map.engine;
    selectionChange(-1);say("Mapa importado: "+notes.length+" eventos. Edite e exporte MIDI.");
  }
  $("map-file").addEventListener("change",async event=>{
    try{const f=event.target.files?.[0];if(f)await ingest(f);}
    catch(e){say("Importação bloqueada: "+e.message);}
  });
  $("audio-file").addEventListener("change",async event=>{
    try{const f=event.target.files?.[0];if(f)await ingest(f);}
    catch(e){say("Áudio bloqueado: "+e.message);}
  });
  document.getElementById("dropzone").addEventListener("dragover",e=>e.preventDefault());
  document.getElementById("dropzone").addEventListener("drop",async e=>{
    e.preventDefault();try{for(const f of e.dataTransfer.files) await ingest(f);}
    catch(err){say("Arquivo rejeitado: "+err.message);}
  });
  $("bpm").addEventListener("change",e=>{
    bpm=Math.max(30,Math.min(300,Math.round(+e.target.value||120)));draw();
  });
  $("zoom").addEventListener("input",e=>{zoom=+e.target.value;draw();});
  $("quantize").addEventListener("click",()=>{
    historyPush();notes=quantizeNotes(notes,bpm,4);selectionChange(-1);say("Notas quantizadas em semicolcheias.");
  });
  $("undo").addEventListener("click",()=>{
    if(!history.length)return;future.push(clone(notes));notes=history.pop();selectionChange(-1);
  });
  $("redo").addEventListener("click",()=>{
    if(!future.length)return;history.push(clone(notes));notes=future.pop();selectionChange(-1);
  });
  $("delete").addEventListener("click",()=>{
    if(selected<0)return;historyPush();notes.splice(selected,1);selectionChange(-1);
  });
  $("export-midi").addEventListener("click",()=>{
    try{exportFile(encodeMidi(notes,bpm),"HAZEWAVE-edited.mid","audio/midi");
      say("MIDI exportado localmente • "+notes.length+" notas");}
    catch(e){say("Exportação bloqueada: "+e.message);}
  });
  $("export-json").addEventListener("click",()=>{
    exportFile(JSON.stringify({schema:"HazewaveEditedNoteMap/v1",source,engine,
      tempo_bpm:bpm,notes},null,2),"HAZEWAVE-edited-notes.json","application/json");
  });
  $("preview").addEventListener("click",async ()=>{
    try{
      if(ac)await ac.close();
      playTimers.forEach(clearTimeout);playTimers=[];
      ac=new window.AudioContext();
      await ac.resume();
      const t0=ac.currentTime+0.09;
      for(const n of notes.slice(0,1500)){
        const osc=ac.createOscillator(),env=ac.createGain();
        osc.type="sine";osc.frequency.value=440*Math.pow(2,(n.midi_note-69)/12);
        const a=t0+n.start_seconds,b=t0+n.end_seconds;
        env.gain.setValueAtTime(0,a);
        env.gain.linearRampToValueAtTime(Math.min(.16,n.velocity/127*.17),a+.01);
        env.gain.setValueAtTime(Math.min(.16,n.velocity/127*.17),Math.max(a+.012,b-.02));
        env.gain.linearRampToValueAtTime(0,b);
        osc.connect(env).connect(ac.destination);osc.start(a);osc.stop(b+.02);
      }
      say("Prévia sintetizada das notas editadas — não é o áudio original.");
    }catch(e){say("Áudio indisponível: "+e.message);}
  });
  grid.addEventListener("contextmenu",e=>e.preventDefault());
  grid.addEventListener("pointerdown",e=>{
    if(e.button!==0)return;
    const rect=grid.getBoundingClientRect();
    const x=e.clientX-rect.left,y=e.clientY-rect.top;
    const target=e.target.closest(".note");
    if(target){
      const index=Number(target.dataset.index);selectionChange(index);
      const before={...notes[index]};historyPush();
      const resizing=x-(before.start_seconds*zoom+(before.end_seconds-before.start_seconds)*zoom)>-14;
      const origin={x,y};
      const move=ev=>{
        const dx=ev.clientX-e.clientX,dy=ev.clientY-e.clientY;
        const delta=Math.round(dy/ROW);
        const n=notes[index];if(!n)return;
        if(resizing){
          n.end_seconds=Math.max(n.start_seconds+60/bpm/8,
            xToTime(before.end_seconds*zoom+dx));
        }else{
          const duration=before.end_seconds-before.start_seconds;
          n.start_seconds=xToTime(before.start_seconds*zoom+dx);
          n.end_seconds=n.start_seconds+duration;
          n.midi_note=Math.max(0,Math.min(127,before.midi_note-delta));
        }
        draw();
      };
      const up=()=>{
        window.removeEventListener("pointermove",move);
        window.removeEventListener("pointerup",up);
        say("Evento editado • MIDI disponível para exportação.");
      };
      window.addEventListener("pointermove",move);window.addEventListener("pointerup",up,{once:true});
    } else {
      const pitch=yToPitch(y);
      if(pitch<LOW||pitch>HIGH)return;
      historyPush();
      const start=xToTime(x);
      notes.push({midi_note:pitch,start_seconds:start,
        end_seconds:start+60/bpm/4,velocity:90});
      selectionChange(notes.length-1);
    }
  });
  window.addEventListener("keydown",e=>{
    if(e.target.matches("input"))return;
    if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="z"){
      e.preventDefault();$("undo").click();
    }
    if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="y"){
      e.preventDefault();$("redo").click();
    }
    if(e.key==="Delete"||e.key==="Backspace")$("delete").click();
  });
  draw();say("Pronto • importe um mapa JSON gerado por hazewave notes.");
}
if (typeof document!=="undefined") {
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",launch);
  else launch();
}

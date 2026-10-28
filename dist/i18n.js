export const LANGUAGES = ['en', 'zh', 'fr', 'es', 'ar'];
const DEFAULT_LANGUAGE = 'en';
const storageKey = 'matchlens-language', catalogs = new Map();
let currentLanguage = DEFAULT_LANGUAGE, dictionary = {}, changeVersion = 0;
try {
  const saved = new URLSearchParams(location.search).get('lang') || localStorage.getItem(storageKey) || JSON.parse(localStorage.getItem('matchlens-pocket-layout-v1'))?.audience?.language;
  if (LANGUAGES.includes(saved)) currentLanguage = saved;
} catch {}
const initialLanguage = currentLanguage;
const sourceLabels = await fetch(new URL('./i18n-static.json', import.meta.url)).then(response => response.json());
const originalText = new WeakMap(), originalAttributes = new WeakMap();
const mediaControls = new WeakMap(), fileControls = new WeakMap();
export function language() { return currentLanguage; }
export function t(key, values = {}) {
  if (!(key in dictionary)) throw new Error(`Missing translation: ${currentLanguage}/${key}`);
  return dictionary[key].replace(/\{(\w+)(?::[^}]*)?\}/g, (_, name) => values[name] ?? dictionary['common.unknown']);
}
export function eventLabel(kind) { return dictionary[`event.${kind}`] || t('event.object'); }
export function displayName(name) {
  const track=/^Team ([AU]) · track (\d+)$/.exec(name), team=/^Team ([AU])$/.exec(name);
  return track?t('name.anonymous',{team:track[1],track:track[2]}):team?t('name.team',{team:team[1]}):name;
}
export function localizedError(key, values) { const error = new Error(t(key, values)); error.localized = true; return error; }
export function errorText(error) {
  if (error?.localized) return error.message;
  console.error(error);
  return t(error instanceof SyntaxError ? 'error.invalid_json' : error instanceof TypeError ? 'error.connection' : 'error.generic');
}
function updateNativeControls(root) {
  for (const input of root.querySelectorAll('input[type="file"]')) {
    let controls=fileControls.get(input);
    if(!controls){
      const wrapper=document.createElement('span'),button=document.createElement('button'),name=document.createElement('span');
      wrapper.className='localized-file-picker';button.type='button';input.hidden=true;
      button.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();input.click();});
      controls={button,name};fileControls.set(input,controls);wrapper.append(button,name);input.after(wrapper);
      input.addEventListener('change',()=>{name.textContent=input.files?.[0]?.name||t('ui.no_file');});
    }
    controls.button.textContent=t('ui.choose_file');controls.name.textContent=input.files?.[0]?.name||t('ui.no_file');
  }
  for(const video of root.querySelectorAll('video')){
    let controls=mediaControls.get(video);
    if(!controls){
      const wrapper=document.createElement('div'),button=document.createElement('button'),seek=document.createElement('input'),time=document.createElement('bdi'),error=document.createElement('span');
      const mute=document.createElement('button'),volume=document.createElement('input'),rate=document.createElement('select'),fullscreen=document.createElement('button');
      mute.type=fullscreen.type='button';volume.type='range';volume.min='0';volume.max='1';volume.step='0.05';volume.className='media-volume';
      for(const speed of [0.25,0.5,0.75,1,1.25,1.5,2])rate.append(new Option(speed+'×',String(speed)));
      wrapper.className='localized-media-controls';button.type='button';seek.type='range';seek.min='0';seek.max='0';seek.step='0.01';seek.value='0';time.dir='ltr';error.className='media-error';error.hidden=true;
      video.controls=false;video.removeAttribute('controls');
      let mediaFailed=false;
      const position=seconds=>`${String(Math.floor(seconds/60)).padStart(2,'0')}:${String(Math.floor(seconds%60)).padStart(2,'0')}`;
      const refresh=()=>{video.hidden=mediaFailed||!video.getAttribute('src');const duration=Number.isFinite(video.duration)?video.duration:0;button.textContent=t(video.paused?'ui.play':'ui.pause');button.disabled=!duration;seek.disabled=!duration;seek.max=String(duration);seek.value=String(video.currentTime||0);seek.setAttribute('aria-label',t('media.seek'));time.textContent=`${position(video.currentTime||0)} / ${position(duration)}`;error.textContent=t('media.error');video.setAttribute('aria-label',t('media.preview'));mute.textContent=t(video.muted?'media.unmute':'media.mute');mute.disabled=!duration;volume.value=String(video.volume);volume.disabled=!duration;volume.setAttribute('aria-label',t('media.volume'));rate.value=String(video.playbackRate);rate.setAttribute('aria-label',t('ui.speed'));fullscreen.textContent=t('media.fullscreen');fullscreen.disabled=!duration||!video.requestFullscreen;};
      button.addEventListener('click',async()=>{if(video.paused){try{await video.play();error.hidden=true;}catch{error.hidden=false;}}else video.pause();refresh();});
      seek.addEventListener('input',()=>{if(Number.isFinite(video.duration))video.currentTime=Number(seek.value);});
      mute.addEventListener('click',()=>{video.muted=!video.muted;refresh();});volume.addEventListener('input',()=>{video.volume=Number(volume.value);video.muted=false;});rate.addEventListener('change',()=>{video.playbackRate=Number(rate.value);});fullscreen.addEventListener('click',()=>{video.requestFullscreen?.().catch(error=>console.error(error));});
      for(const event of ['timeupdate','loadedmetadata','play','pause','ended','durationchange','volumechange','ratechange'])video.addEventListener(event,refresh);
      video.addEventListener('error',()=>{mediaFailed=!!video.getAttribute('src');error.hidden=!mediaFailed;refresh();});video.addEventListener('loadstart',()=>{mediaFailed=false;error.hidden=true;refresh();});video.addEventListener('emptied',()=>{mediaFailed=false;error.hidden=true;refresh();});
      wrapper.append(button,seek,time,mute,volume,rate,fullscreen,error);(video.closest('.preview')||video).after(wrapper);controls={refresh};mediaControls.set(video,controls);
    }
    controls.refresh();
  }
}
export function applyTranslations(root = document) {
  for (const node of root.querySelectorAll('[data-i18n]')) node.textContent = t(node.dataset.i18n);
  for (const attribute of ['aria-label', 'alt', 'title', 'placeholder'])
    for (const node of root.querySelectorAll(`[data-i18n-${attribute}]`)) node.setAttribute(attribute, t(node.getAttribute(`data-i18n-${attribute}`)));
  const walker = document.createTreeWalker(root === document ? document.documentElement : root, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode, parent = node.parentElement;
    if (!parent || parent.closest('script,style,textarea,pre,[data-i18n],[data-i18n-dynamic]')) continue;
    const original = originalText.get(node) ?? node.textContent; originalText.set(node, original);
    const label=original.trim(), plain=label.replace(/^·\s*/,''), key=sourceLabels[label]||sourceLabels[plain];
    if (key) node.textContent = original.replace(sourceLabels[label]?label:plain,t(key));
  }
  for (const node of root.querySelectorAll('[aria-label],[alt],[title],[placeholder]')) {
    let values = originalAttributes.get(node);
    if (!values) { values = {}; originalAttributes.set(node, values); }
    for (const attribute of ['aria-label','alt','title','placeholder']) {
      if (!node.hasAttribute(attribute) || node.hasAttribute(`data-i18n-${attribute}`)) continue;
      const original = values[attribute] ?? node.getAttribute(attribute); values[attribute] = original;
      if (sourceLabels[original]) node.setAttribute(attribute, t(sourceLabels[original]));
    }
  }
  for (const select of root.querySelectorAll('[data-language-select]')) {
    select.replaceChildren(...LANGUAGES.map(code => new Option(t(`language.${code}`), code))); select.value = currentLanguage;
  }
  updateNativeControls(root);
  document.documentElement.lang = currentLanguage;
  document.documentElement.dir = currentLanguage === 'ar' ? 'rtl' : 'ltr';
  document.documentElement.dataset.i18nReady = 'true';
  for(const anchor of root.querySelectorAll('a[href]')){
    const url=new URL(anchor.getAttribute('href'),location.href);
    if(url.origin===location.origin&&['/','/index.html','/sources.html','/video-lab.html','/overlay.html'].includes(url.pathname)){
      url.searchParams.set('lang',currentLanguage);anchor.href=url.pathname+url.search+url.hash;
    }
  }
  document.title = `MatchLens · ${t(document.body.dataset.pageTitle || 'app.subtitle')}`;
  document.querySelector('meta[name="description"]')?.setAttribute('content',t('app.description'));
}
export function addLanguagePicker(target) {
  const label=document.createElement('label'), caption=document.createElement('span'), select=document.createElement('select');
  label.className='language-picker';caption.dataset.i18n='ui.language';select.dataset.languageSelect='';
  label.append(caption,select);target.append(label);applyTranslations(label);
}
export async function setLanguage(code, {persist = true} = {}) {
  if (!LANGUAGES.includes(code)) code = DEFAULT_LANGUAGE;
  const version = ++changeVersion;
  if (!catalogs.has(code)) {
    const response = await fetch(new URL(`./locales/${code}.json`, import.meta.url));
    if (!response.ok) throw new Error(`Unable to load locale ${code}`);
    catalogs.set(code, await response.json());
  }
  if (version !== changeVersion) return;
  currentLanguage = code; dictionary = catalogs.get(code);
  if (persist) {
    try { localStorage.setItem(storageKey, code); } catch {}
    const url = new URL(location.href);
    url.searchParams.set('lang', code);
    history.replaceState(history.state, '', url);
  }
  applyTranslations();
  document.dispatchEvent(new CustomEvent('matchlens:language', {detail: {language: code}}));
}
await setLanguage(initialLanguage, {persist: false});
document.addEventListener('change', event => {
  if (event.target.matches('[data-language-select]')) setLanguage(event.target.value).catch(error => console.error(error));
});
window.addEventListener('storage', event => {
  if (event.key === storageKey && LANGUAGES.includes(event.newValue)) setLanguage(event.newValue, {persist:false}).catch(error => console.error(error));
});

(() => {
  'use strict';
  const limit = Number(document.body.dataset.previewCharacters) || 300;
  document.querySelectorAll('[data-readmore]').forEach((node, index) => {
    const text = node.textContent.trim();
    if (text.length <= limit) return;
    const original = node.innerHTML, preview = text.slice(0, limit).trimEnd() + '…';
    node.textContent = preview; node.classList.add('readmore-copy');
    node.id = node.id || `expanded-text-${index}`;
    const button = document.createElement('button'); button.type = 'button'; button.className = 'readmore-button';
    button.textContent = 'Read more'; button.setAttribute('aria-controls', node.id); button.setAttribute('aria-expanded','false');
    button.addEventListener('click', () => { const expanded = button.getAttribute('aria-expanded') !== 'true';
      if (expanded) node.innerHTML = original; else node.textContent = preview;
      button.setAttribute('aria-expanded',String(expanded));button.textContent = expanded ? 'Read less' : 'Read more';
    }); node.after(button);
  });
  document.addEventListener('click', event => {
    const photo = event.target.closest('[data-photo]');
    if (photo) {
      const lightbox = document.querySelector('#lb');
      if (lightbox) { const img=lightbox.querySelector('img');img.src=photo.dataset.photo;img.alt=photo.dataset.caption||'';lightbox.querySelector('p').textContent=photo.dataset.caption||'';lightbox.hidden=false; }
    }
    const button = event.target.closest('.lazy-video button');
    if (button) {
      const video=button.closest('[data-youtube]'), id=video.dataset.youtube;
      if (!/^[A-Za-z0-9_-]{11}$/.test(id)) return;
      const iframe=document.createElement('iframe');iframe.src=`https://www.youtube-nocookie.com/embed/${id}`;
      iframe.title=button.textContent.trim();iframe.allow='encrypted-media; picture-in-picture';iframe.allowFullscreen=true;iframe.referrerPolicy='strict-origin-when-cross-origin';
      video.replaceChildren(iframe);
    }
  });
  const consent=document.querySelector('#visit-consent');
  const cookie=name=>document.cookie.split('; ').find(part=>part.startsWith(name+'='))?.split('=')[1];
  if (consent && !cookie('sai_analytics')) consent.hidden=false;
  document.querySelectorAll('[data-reset-consent]').forEach(button=>button.addEventListener('click',()=>{if(consent)consent.hidden=false;}));
  document.querySelectorAll('[data-consent]').forEach(button=>button.addEventListener('click',()=>{
    const secure=location.protocol==='https:'?'; Secure':'';
    document.cookie=`sai_analytics=${button.dataset.consent}; Path=/; Max-Age=15552000; SameSite=Lax${secure}`;
    if(button.dataset.consent==='yes'&&!cookie('sai_visitor')) {
      const id=crypto.randomUUID?crypto.randomUUID():'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g,c=>{const r=Math.random()*16|0;return(c==='x'?r:(r&3|8)).toString(16);});
      document.cookie=`sai_visitor=${id}; Path=/; Max-Age=15552000; SameSite=Lax${secure}`;
    }
    if(button.dataset.consent==='no') document.cookie=`sai_visitor=; Path=/; Max-Age=0; SameSite=Lax${secure}`;
    consent.hidden=true;
  }));
  const helper=document.querySelector('#journey-helper'), toggle=document.querySelector('.journey-helper-button');
  if(helper&&toggle) {
    const close=()=>{helper.hidden=true;toggle.setAttribute('aria-expanded','false');toggle.focus();};
    toggle.addEventListener('click',()=>{helper.hidden=!helper.hidden;toggle.setAttribute('aria-expanded',String(!helper.hidden));if(!helper.hidden)helper.querySelector('input').focus();});
    helper.querySelector('.helper-close').addEventListener('click',close);
    helper.addEventListener('keydown',event=>{if(event.key==='Escape')close();});
    const input=helper.querySelector('input'),results=helper.querySelector('#helper-results');let timer,controller;
    input.addEventListener('input',()=>{clearTimeout(timer);if(controller)controller.abort();results.replaceChildren();const query=input.value.trim();if(query.length<2)return;
      timer=setTimeout(async()=>{try{controller=new AbortController();const response=await fetch('/api/journeys/?q='+encodeURIComponent(query),{signal:controller.signal});const data=await response.json();results.replaceChildren();
        if(!data.results.length){const p=document.createElement('p');p.textContent='No matches yet. Our team can help with a custom journey.';results.append(p);}
        data.results.forEach(item=>{const link=document.createElement('a');link.href=item.url;link.textContent=item.title+' · '+item.duration;results.append(link);});
      }catch(error){if(error.name!=='AbortError')results.textContent='Please use the search button or contact our team.';}},250);
    });
  }
})();

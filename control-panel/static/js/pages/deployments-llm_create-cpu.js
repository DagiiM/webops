/* Public model discovery and compatibility; all authoritative checks are server-side. */
(() => {
    const form = document.getElementById('cpuLlmForm');
    if (!form) return;
    const input = document.getElementById('cpuModel');
    const out = document.getElementById('compatibility');
    const btn = document.getElementById('checkModel');
    const deploy = document.getElementById('cpuDeploy');
    const catalog = document.getElementById('hfCatalogSearch');
    const results = document.getElementById('hfCatalogResults');
    const status = document.getElementById('hfCatalogStatus');
    const query = document.getElementById('hfCatalogQuery');
    let checkSeq = 0, searchSeq = 0;
    function resetCheck() {
        ++checkSeq;
        out.textContent = '';
        deploy.disabled = true;
        btn.disabled = false;
    }
    input.addEventListener('input', resetCheck);
    async function check() {
        if (!input.reportValidity()) return;
        const seq = ++checkSeq, model = input.value.trim();
        btn.disabled = true; deploy.disabled = true;
        out.textContent = 'Checking model metadata and available resources…';
        try {
            const body = new URLSearchParams({model_name:model,csrfmiddlewaretoken:form.querySelector('[name=csrfmiddlewaretoken]').value});
            const r = await fetch(form.dataset.urlDetect,{method:'POST',body,headers:{Accept:'application/json'}});
            const d = await r.json();
            if (seq !== checkSeq || input.value.trim() !== model) return;
            const details = d.estimated_ram_gb != null ? ' Estimated RAM '+d.estimated_ram_gb+' GB; weights '+d.weights_gb+' GB. ' : '';
            out.textContent = (d.success?'Compatible. ':'Not compatible. ')+details+(d.errors||[d.error||'']).join(' ')+' '+(d.warnings||[]).join(' ');
            deploy.disabled = !r.ok || !d.success;
        } catch (_) {
            if (seq === checkSeq) out.textContent = 'Compatibility could not be verified. Try again.';
        } finally { if (seq === checkSeq) btn.disabled = false; }
    }
    btn.addEventListener('click',check);
    form.addEventListener('submit',e=>{if(deploy.disabled){e.preventDefault();check();}});
    function node(tag,text,classes) {
        const el=document.createElement(tag);el.textContent=text;
        if(classes)el.className=classes;
        return el;
    }
    function render(models) {
        results.replaceChildren();
        for (const m of models) {
            const card=node('div','','webops-card webops-mb-sm');
            const body=node('div','','webops-card-body');
            body.append(node('strong',m.id));
            const details=[m.reviewed?'Reviewed CPU catalog':'Not reviewed for this host',m.safetensors?'Safetensors':'Weight format not confirmed'];
            if(m.parameters!=null)details.push(new Intl.NumberFormat().format(m.parameters)+' parameters');
            if(m.downloads!=null)details.push(new Intl.NumberFormat().format(m.downloads)+' downloads');
            body.append(node('p',details.join(' · '),'webops-text-muted'));
            const choose=node('button',m.reviewed?'Select and check':'Check requirements','webops-btn webops-btn-secondary');
            choose.type='button';choose.dataset.hfModel=m.id;
            const link=node('a','View model on Hugging Face','webops-text-primary webops-ml-sm');
            link.href='https://huggingface.co/'+m.id.split('/').map(encodeURIComponent).join('/');
            link.target='_blank';link.rel='noopener noreferrer';
            body.append(choose,link);card.append(body);results.append(card);
        }
    }
    async function search(q) {
        const seq=++searchSeq;
        status.textContent='Loading public models from Hugging Face…';
        try {
            const url=new URL(catalog.dataset.urlSearch,location.origin);
            if(q)url.searchParams.set('q',q);
            const response=await fetch(url,{headers:{Accept:'application/json'}});
            const data=await response.json();
            if(seq!==searchSeq)return;
            if(!response.ok)throw new Error(data.error||'Catalog unavailable.');
            render(data.models);
            status.textContent=data.models.length ? data.models.length+' model(s) from Hugging Face'+(data.partial?' (some metadata unavailable).':'.') : 'No matching public text-generation models found.';
        }catch(e){
            if(seq===searchSeq)status.textContent=(e.message||'Catalog unavailable.')+' Previous choices remain available.';
        }
    }
    results.addEventListener('click',e=>{
        const target=e.target.closest('[data-hf-model]');if(!target)return;
        input.value=target.dataset.hfModel;resetCheck();
        const name=document.getElementById('cpuName');
        if(!name.value)name.value=input.value.split('/').pop().toLowerCase().replace(/[^a-z0-9_-]/g,'-').slice(0,100);
        input.focus();check();
    });
    catalog.addEventListener('submit',e=>{e.preventDefault();search(query.value.trim());});
    document.getElementById('hfCatalogReset').addEventListener('click',()=>{query.value='';search('');});
    search('');
})();

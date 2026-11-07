(function(){
  function get(k){try{return localStorage.getItem(k)}catch(e){return null}}
  function set(k,v){try{localStorage.setItem(k,v)}catch(e){}}
  var root=document.documentElement;
  document.querySelectorAll('[data-act]').forEach(function(b){
    b.addEventListener('click',function(){
      var a=b.getAttribute('data-act');
      if(a==='dark'){var d=document.body.classList.toggle('dark');set('jing-dark',d?'1':'0');return}
      var cur=parseInt(getComputedStyle(root).getPropertyValue('--fs'))||19;
      cur=Math.max(14,Math.min(28,cur+(a==='bigger'?1:-1)));
      root.style.setProperty('--fs',cur+'px');set('jing-fs',cur);
    });
  });
  var reader=document.querySelector('.reader');
  var read={};try{read=JSON.parse(get('jing-read')||'{}')}catch(e){}
  if(reader){
    var slug=reader.getAttribute('data-slug');
    read[slug]=1;set('jing-read',JSON.stringify(read));
    set('jing-last',JSON.stringify({slug:slug,title:reader.getAttribute('data-title')}));
    document.addEventListener('keydown',function(e){
      if(e.altKey||e.ctrlKey||e.metaKey)return;
      var l=null;
      if(e.key==='ArrowLeft')l=document.querySelector('link[rel=prev]');
      if(e.key==='ArrowRight')l=document.querySelector('link[rel=next]');
      if(l)location.href=l.getAttribute('href');
    });
  }
  document.querySelectorAll('.toc a').forEach(function(a){
    if(read[a.getAttribute('href')])a.classList.add('read');
  });
  var r=document.getElementById('resume');
  if(r){var last=null;try{last=JSON.parse(get('jing-last')||'null')}catch(e){}
    if(last&&last.slug){r.href=last.slug;r.textContent='继续：'+last.title;r.hidden=false}}
})();

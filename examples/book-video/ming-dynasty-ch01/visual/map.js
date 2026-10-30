/** Deterministic SVG arc-length samples keep the traveler on the drawn route. */
window.buildMingMap=function(tl){
  const route=document.querySelector('#S05 .route');
  const length=route.getTotalLength();
  const origin=route.getPointAtLength(0);
  const samples=Array.from({length:120},(_,i)=>{
    const p=route.getPointAtLength(length*(i+1)/120);
    return {x:p.x-origin.x,y:p.y-origin.y,duration:9/120,ease:'none'};
  });
  route.style.strokeDasharray=String(length);
  tl.from('#S05 .route',{strokeDashoffset:length,duration:9,ease:'none'},44);
  tl.to('#S05 .traveler',{keyframes:samples,duration:9,ease:'none'},44);
  tl.from('#S05 .map',{opacity:0,y:20,duration:1,ease:'power2.out'},44);
};

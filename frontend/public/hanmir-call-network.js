let socket,audio,dropped=0,tick=0;
self.onmessage=({data})=>{
  if(data.kind==='init'){
    audio=data.port;
    audio.onmessage=({data:m})=>{
      if(m.type!=='mic'||socket?.readyState!==WebSocket.OPEN)return;
      if(socket.bufferedAmount<=6400)socket.send(m.pcm);
      else{dropped+=m.pcm.byteLength/2;self.postMessage({kind:'dropped',samples:dropped});}
    };
    socket=new WebSocket(data.url);socket.binaryType='arraybuffer';
    socket.onopen=()=>self.postMessage({kind:'state',readyState:1});
    socket.onmessage=({data:m})=>{
      if(typeof m==='string'){
        try{const c=JSON.parse(m);if(c.type==='call_status')audio.postMessage({type:'enabled',value:c.status==='connected'});}catch{}
        self.postMessage({kind:'message',data:m});
      }else if(m instanceof ArrayBuffer){
        audio.postMessage({type:'audio',pcm:m},[m]);
        if(performance.now()-tick>=100){tick=performance.now();self.postMessage({kind:'message',data:'{"type":"call_audio_tick"}'});}
      }
    };
    socket.onerror=()=>self.postMessage({kind:'error'});
    socket.onclose=({code,reason,wasClean})=>{audio.postMessage({type:'enabled',value:false});self.postMessage({kind:'close',code,reason,wasClean});};
  }else if(data.kind==='send'&&socket?.readyState===WebSocket.OPEN){
    let m=data.data;
    if(typeof m==='string')try{const c=JSON.parse(m);if(c.type==='call_audio_metrics'){c.metrics.webDroppedSamples=dropped;m=JSON.stringify(c);}}catch{}
    socket.send(m);
  }else if(data.kind==='close')socket?.close();
};

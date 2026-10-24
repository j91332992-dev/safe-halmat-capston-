export class CallWorkerSocket {
  readyState:number=WebSocket.CONNECTING;
  bufferedAmount=0;
  binaryType:BinaryType='arraybuffer';
  onmessage:((e:MessageEvent)=>void)|null=null;
  onerror:((e:Event)=>void)|null=null;
  onclose:((e:CloseEvent)=>void)|null=null;
  private worker:Worker;
  constructor(url:string,node:AudioWorkletNode,onDropped:(n:number)=>void){
    this.worker=new Worker(`${import.meta.env.BASE_URL}hanmir-call-network.js`);
    const channel=new MessageChannel();
    node.port.postMessage({type:'network',port:channel.port1},[channel.port1]);
    this.worker.onmessage=({data:m})=>{
      if(m.kind==='state')this.readyState=m.readyState;
      else if(m.kind==='message')this.onmessage?.(new MessageEvent('message',{data:m.data}));
      else if(m.kind==='dropped')onDropped(m.samples);
      else if(m.kind==='error')this.onerror?.(new Event('error'));
      else if(m.kind==='close'){this.readyState=WebSocket.CLOSED;this.onclose?.(new CloseEvent('close',{code:m.code,reason:m.reason,wasClean:m.wasClean}));this.worker.terminate();}
    };
    this.worker.onerror=()=>this.onerror?.(new Event('error'));
    this.worker.postMessage({kind:'init',url,port:channel.port2},[channel.port2]);
  }
  send(data:string|ArrayBuffer){this.worker.postMessage({kind:'send',data});}
  close(){this.readyState=WebSocket.CLOSING;this.worker.postMessage({kind:'close'});const w=this.worker;window.setTimeout(()=>w.terminate(),2000);}
}

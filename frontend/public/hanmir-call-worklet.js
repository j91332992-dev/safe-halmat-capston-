/* PCM16/16k protocol is unchanged. Audio runs on the browser rendering thread. */
class HanmirCallProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ring = new Float32Array(3200); // hard cap: 200 ms at 16 kHz
    this.head = this.count = this.phase = 0;
    this.playing = this.enabled = false;
    this.lastOutput = this.ramp = 0;
    this.tx = new Int16Array(320);
    this.txUsed = this.inputIndex = this.nextSample = this.previousInput = 0;
    this.stats = {rxSamples:0, rxClipped:0, overflowSamples:0, underrunOutputSamples:0,
      rebufferCount:0, txSamples:0, txClipped:0, txPeak:0, rxPeak:0, txSquare:0};
    this.reportAt = currentFrame + sampleRate * 5;
    const receive = ({data}) => {
      if(data.type==='network'){this.network=data.port;this.network.onmessage=receive;return;}
      if (data.type === 'enabled') {
        this.enabled = !!data.value;
        this.head = this.count = this.phase = this.ramp = this.lastOutput = 0;
        this.playing = false;
        this.txUsed = this.inputIndex = this.nextSample = this.previousInput = 0;
      } else if (data.type === 'audio' && data.pcm instanceof ArrayBuffer && this.enabled) {
        const pcm = new Int16Array(data.pcm);
        for (let i=0;i<pcm.length;i++) {
          const value=pcm[i]/32768;
          this.stats.rxSamples++;
          if (Math.abs(pcm[i])>=32767) this.stats.rxClipped++;
          this.stats.rxPeak=Math.max(this.stats.rxPeak,Math.abs(value));
          if (this.count===this.ring.length) {
            this.head=(this.head+1)%this.ring.length; this.count--;
            this.stats.overflowSamples++;
            this.ramp=0;
          }
          this.ring[(this.head+this.count)%this.ring.length]=value;
          this.count++;
        }
      }
    };
    this.port.onmessage=receive;
  }
  process(inputs,outputs) {
    const input=inputs[0]?.[0], output=outputs[0]?.[0];
    if (this.enabled && input) {
      const step=sampleRate/16000;
      for (let i=0;i<input.length;i++,this.inputIndex++) {
        const value=input[i];
        while (this.nextSample<=this.inputIndex) {
          const fraction=this.nextSample-(this.inputIndex-1);
          const v=this.previousInput+(value-this.previousInput)*fraction;
          this.stats.txSamples++;this.stats.txSquare+=v*v;
          this.stats.txPeak=Math.max(this.stats.txPeak,Math.abs(v));
          if (Math.abs(v)>=.999) this.stats.txClipped++;
          const bounded=Math.max(-1,Math.min(1,v));
          this.tx[this.txUsed++]=bounded<0?bounded*32768:bounded*32767;
          this.nextSample+=step;
          if (this.txUsed===320) {
            (this.network || this.port).postMessage({type:'mic',pcm:this.tx.buffer},[this.tx.buffer]);
            this.tx=new Int16Array(320);this.txUsed=0;
          }
        }
        this.previousInput=value;
      }
    }
    if (output) for (let i=0;i<output.length;i++) {
      if (!this.enabled) {output[i]=0;continue;}
      if (!this.playing && this.count>=960) {this.playing=true;this.phase=0;this.ramp=0;}
      if (this.playing && this.count>=2) {
        const a=this.ring[this.head], b=this.ring[(this.head+1)%this.ring.length];
        this.ramp=Math.min(1,this.ramp+1/(sampleRate*.005));
        this.lastOutput=(a+(b-a)*this.phase)*this.ramp;
        output[i]=this.lastOutput;
        this.phase+=16000/sampleRate;
        while(this.phase>=1 && this.count) {this.phase--;this.head=(this.head+1)%this.ring.length;this.count--;}
      } else {
        if(this.playing){this.stats.rebufferCount++;this.playing=false;this.ramp=0;}
        this.stats.underrunOutputSamples++;
        this.lastOutput*=.98;output[i]=this.lastOutput;
      }
    }
    if (currentFrame>=this.reportAt) {
      this.port.postMessage({type:'stats',...this.stats,queueMs:this.count/16,
        txRms:Math.sqrt(this.stats.txSquare/Math.max(1,this.stats.txSamples)),outputRate:sampleRate});
      this.reportAt=currentFrame+sampleRate*5;
    }
    return true;
  }
}
registerProcessor('hanmir-call',HanmirCallProcessor);

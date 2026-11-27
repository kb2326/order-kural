// Live voice over /api/voice: microphone -> 16 kHz PCM16 -> server; server speech PCM16 -> speakers.
// Plain JS, no build step. Exposes window.KuralVoice.

(function () {
  const RATE = 16000;
  const WORKLET = `class Mic extends AudioWorkletProcessor {
    constructor() { super(); this.buf = []; this.step = sampleRate / ${RATE}; this.pos = 0; }
    process(inputs) {
      const ch = inputs[0] && inputs[0][0];
      if (!ch) return true;
      for (let i = 0; i < ch.length; i++) {
        this.pos += 1;
        if (this.pos >= this.step) { this.pos -= this.step; this.buf.push(Math.max(-1, Math.min(1, ch[i]))); }
      }
      if (this.buf.length >= 320) {
        const out = new Int16Array(this.buf.length);
        for (let i = 0; i < out.length; i++) out[i] = this.buf[i] * 32767;
        this.port.postMessage(out.buffer, [out.buffer]);
        this.buf = [];
      }
      return true;
    }
  }
  registerProcessor('kural-mic', Mic);`;

  class KuralVoice {
    constructor(onEvent) {
      this.onEvent = onEvent;
      this.ws = null;
      this.ctx = null;
      this.stream = null;
      this.playAt = 0;
      this.playing = [];
    }

    get open() { return this.ws && this.ws.readyState === WebSocket.OPEN; }

    async start(session, lang) {
      this.ctx = new AudioContext();
      const url = URL.createObjectURL(new Blob([WORKLET], { type: "application/javascript" }));
      await this.ctx.audioWorklet.addModule(url);
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      const proto = location.protocol === "https:" ? "wss://" : "ws://";
      const q = new URLSearchParams({ session, lang });
      this.ws = new WebSocket(`${proto}${location.host}/api/voice?${q}`);
      this.ws.binaryType = "arraybuffer";
      this.ws.onmessage = (e) => {
        if (typeof e.data === "string") {
          const msg = JSON.parse(e.data);
          if (msg.type === "clear") this.stopPlayback();
          this.onEvent(msg);
        } else {
          this.play(e.data);
        }
      };
      this.ws.onclose = (e) => { this.cleanup(); this.onEvent({ type: "closed", code: e.code, reason: e.reason }); };
      const source = this.ctx.createMediaStreamSource(this.stream);
      const node = new AudioWorkletNode(this.ctx, "kural-mic");
      node.port.onmessage = (e) => { if (this.open) this.ws.send(e.data); };
      source.connect(node);
    }

    send(obj) { if (this.open) this.ws.send(JSON.stringify(obj)); }

    play(buffer) {
      const pcm = new Int16Array(buffer);
      const f32 = new Float32Array(pcm.length);
      for (let i = 0; i < pcm.length; i++) f32[i] = pcm[i] / 32768;
      const audio = this.ctx.createBuffer(1, f32.length, RATE);
      audio.copyToChannel(f32, 0);
      const src = this.ctx.createBufferSource();
      src.buffer = audio;
      src.connect(this.ctx.destination);
      this.playAt = Math.max(this.playAt, this.ctx.currentTime);
      src.start(this.playAt);
      this.playAt += audio.duration;
      this.playing.push(src);
      src.onended = () => { this.playing = this.playing.filter((s) => s !== src); };
    }

    stopPlayback() {
      for (const s of this.playing) { try { s.stop(); } catch (_) { /* already stopped */ } }
      this.playing = [];
      this.playAt = 0;
    }

    stop() { try { this.ws && this.ws.close(); } catch (_) { /* closed */ } this.cleanup(); }

    cleanup() {
      if (this.stream) this.stream.getTracks().forEach((t) => t.stop());
      if (this.ctx && this.ctx.state !== "closed") this.ctx.close();
      this.stream = null;
    }
  }

  window.KuralVoice = KuralVoice;
})();

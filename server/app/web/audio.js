/* Browser audio → 16 kHz mono 16-bit WAV. Everything stays between this page and our own server. */
const AuraAudio = (() => {
  const TARGET = 16000;
  const MAX_SECONDS = 170;

  function encodeWav(samples) {
    const buf = new ArrayBuffer(44 + samples.length * 2);
    const v = new DataView(buf);
    const str = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
    str(0, "RIFF"); v.setUint32(4, 36 + samples.length * 2, true); str(8, "WAVE"); str(12, "fmt ");
    v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
    v.setUint32(24, TARGET, true); v.setUint32(28, TARGET * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
    str(36, "data"); v.setUint32(40, samples.length * 2, true);
    for (let i = 0; i < samples.length; i++) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      v.setInt16(44 + i * 2, s < 0 ? s * 32768 : s * 32767, true);
    }
    return new Blob([buf], { type: "audio/wav" });
  }

  async function resample(input, rate) {
    if (rate === TARGET) return input;
    const length = Math.max(1, Math.ceil(input.length * TARGET / rate));
    const off = new OfflineAudioContext(1, length, TARGET);
    const buffer = off.createBuffer(1, input.length, rate);
    buffer.copyToChannel(input, 0);
    const src = off.createBufferSource();
    src.buffer = buffer;
    src.connect(off.destination);
    src.start();
    return (await off.startRendering()).getChannelData(0);
  }

  /* Any audio file the browser can decode (WAV, MP3, M4A, OGG…), e.g. AI-voice test clips. */
  async function fileToWav(file) {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    const ctx = new Ctx();
    try {
      const decoded = await ctx.decodeAudioData(await file.arrayBuffer());
      const mono = new Float32Array(decoded.length);
      for (let c = 0; c < decoded.numberOfChannels; c++) {
        const data = decoded.getChannelData(c);
        for (let i = 0; i < data.length; i++) mono[i] += data[i] / decoded.numberOfChannels;
      }
      return encodeWav(await resample(mono, decoded.sampleRate));
    } finally {
      ctx.close();
    }
  }

  class Recorder {
    constructor(onTick) { this.onTick = onTick; this.chunks = []; this.samples = 0; }

    async start() {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) throw new Error("insecure");
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
      const Ctx = window.AudioContext || window.webkitAudioContext;
      this.ctx = new Ctx();
      await this.ctx.resume();
      this.source = this.ctx.createMediaStreamSource(this.stream);
      this.node = this.ctx.createScriptProcessor(4096, 1, 1);
      this.node.onaudioprocess = (e) => {
        const data = new Float32Array(e.inputBuffer.getChannelData(0));
        this.chunks.push(data);
        this.samples += data.length;
        let peak = 0;
        for (let i = 0; i < data.length; i += 16) peak = Math.max(peak, Math.abs(data[i]));
        const seconds = this.samples / this.ctx.sampleRate;
        this.onTick(seconds, Math.min(1, peak * 2.2), seconds >= MAX_SECONDS);
      };
      this.source.connect(this.node);
      this.node.connect(this.ctx.destination);
    }

    release() {
      if (this.node) { this.node.onaudioprocess = null; this.node.disconnect(); }
      if (this.source) this.source.disconnect();
      if (this.stream) this.stream.getTracks().forEach((t) => t.stop());
      if (this.ctx) this.ctx.close();
    }

    async stop() {
      const rate = this.ctx.sampleRate;
      this.release();
      const all = new Float32Array(this.samples);
      let at = 0;
      for (const c of this.chunks) { all.set(c, at); at += c.length; }
      return encodeWav(await resample(all, rate));
    }
  }

  return { Recorder, fileToWav };
})();

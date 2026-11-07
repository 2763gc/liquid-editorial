/**
 * 墨池：WebGL2 稳定流体（Stam 1999 的网格解法）
 *
 * 每帧：涡量 → 散度 → 压力（Jacobi 迭代）→ 减去压力梯度 → 平流速度 → 平流墨
 * 墨（dye）用两个通道：r = 墨，g = 朱砂。显示时按密度梯度加深湿边，像真墨晕开时的「水痕」。
 * 时间步长按真实 dt 计算，耗散按 60fps 归一化，60 / 120 / 144Hz 下手感一致。
 */

const BASE_VERT = `#version 300 es
precision highp float;
in vec2 aPos;
uniform vec2 uTexel;
out vec2 vUv; out vec2 vL; out vec2 vR; out vec2 vT; out vec2 vB;
void main() {
  vUv = aPos * 0.5 + 0.5;
  vL = vUv - vec2(uTexel.x, 0.0); vR = vUv + vec2(uTexel.x, 0.0);
  vT = vUv + vec2(0.0, uTexel.y); vB = vUv - vec2(0.0, uTexel.y);
  gl_Position = vec4(aPos, 0.0, 1.0);
}`;

const HEAD = `#version 300 es
precision highp float;
precision highp sampler2D;
in vec2 vUv; in vec2 vL; in vec2 vR; in vec2 vT; in vec2 vB;
out vec4 o;
`;

const SHADERS = {
  splat: `${HEAD}
uniform sampler2D uTarget; uniform float uAspect; uniform vec3 uColor; uniform vec2 uPoint; uniform float uRadius;
void main() {
  vec2 p = vUv - uPoint; p.x *= uAspect;
  vec3 s = exp(-dot(p, p) / uRadius) * uColor;
  o = vec4(texture(uTarget, vUv).xyz + s, 1.0);
}`,
  advect: `${HEAD}
uniform sampler2D uVelocity; uniform sampler2D uSource; uniform vec2 uTexel; uniform float uDt; uniform float uDissipation;
void main() {
  vec2 coord = vUv - uDt * texture(uVelocity, vUv).xy * uTexel;
  o = uDissipation * texture(uSource, coord);
  o.a = 1.0;
}`,
  divergence: `${HEAD}
uniform sampler2D uVelocity;
void main() {
  float L = texture(uVelocity, vL).x, R = texture(uVelocity, vR).x, T = texture(uVelocity, vT).y, B = texture(uVelocity, vB).y;
  vec2 C = texture(uVelocity, vUv).xy;
  if (vL.x < 0.0) L = -C.x; if (vR.x > 1.0) R = -C.x; if (vT.y > 1.0) T = -C.y; if (vB.y < 0.0) B = -C.y;
  o = vec4(0.5 * (R - L + T - B), 0.0, 0.0, 1.0);
}`,
  curl: `${HEAD}
uniform sampler2D uVelocity;
void main() {
  float L = texture(uVelocity, vL).y, R = texture(uVelocity, vR).y, T = texture(uVelocity, vT).x, B = texture(uVelocity, vB).x;
  o = vec4(0.5 * (R - L - T + B), 0.0, 0.0, 1.0);
}`,
  vorticity: `${HEAD}
uniform sampler2D uVelocity; uniform sampler2D uCurl; uniform float uCurlK; uniform float uDt;
void main() {
  float L = texture(uCurl, vL).x, R = texture(uCurl, vR).x, T = texture(uCurl, vT).x, B = texture(uCurl, vB).x, C = texture(uCurl, vUv).x;
  vec2 f = 0.5 * vec2(abs(T) - abs(B), abs(R) - abs(L));
  f /= length(f) + 0.0001;
  f *= uCurlK * C; f.y *= -1.0;
  vec2 v = texture(uVelocity, vUv).xy + f * uDt;
  o = vec4(clamp(v, -1000.0, 1000.0), 0.0, 1.0);
}`,
  pressure: `${HEAD}
uniform sampler2D uPressure; uniform sampler2D uDivergence;
void main() {
  float L = texture(uPressure, vL).x, R = texture(uPressure, vR).x, T = texture(uPressure, vT).x, B = texture(uPressure, vB).x;
  float d = texture(uDivergence, vUv).x;
  o = vec4((L + R + B + T - d) * 0.25, 0.0, 0.0, 1.0);
}`,
  gradient: `${HEAD}
uniform sampler2D uPressure; uniform sampler2D uVelocity;
void main() {
  float L = texture(uPressure, vL).x, R = texture(uPressure, vR).x, T = texture(uPressure, vT).x, B = texture(uPressure, vB).x;
  vec2 v = texture(uVelocity, vUv).xy - vec2(R - L, T - B);
  o = vec4(v, 0.0, 1.0);
}`,
  fade: `${HEAD}
uniform sampler2D uTex; uniform float uValue;
void main() { o = uValue * texture(uTex, vUv); }`,
  display: `${HEAD}
uniform sampler2D uDye; uniform vec2 uTexel; uniform vec3 uInk; uniform vec3 uRim; uniform float uStrength;
void main() {
  vec3 c = texture(uDye, vUv).rgb;
  float d = clamp(c.r, 0.0, 1.4);
  float vermilion = clamp(c.g, 0.0, 1.0);
  // 湿边：密度梯度越大越深，像墨在宣纸上干透后留下的水痕
  float dl = texture(uDye, vL).r, dr = texture(uDye, vR).r, dt = texture(uDye, vT).r, db = texture(uDye, vB).r;
  float edge = clamp(length(vec2(dr - dl, dt - db)) * 3.2, 0.0, 1.0);
  float a = clamp(1.0 - exp(-d * 1.3) + edge * 0.22, 0.0, 1.0) * uStrength;
  float va = clamp(1.0 - exp(-vermilion * 2.2), 0.0, 1.0) * uStrength;
  vec3 col = mix(uInk, uRim, va / max(a + va, 0.0001));
  float alpha = clamp(a + va * (1.0 - a), 0.0, 1.0);
  o = vec4(col * alpha, alpha);
}`,
} as const;

type ProgName = keyof typeof SHADERS;

interface FBO { tex: WebGLTexture; fbo: WebGLFramebuffer; w: number; h: number }
interface DoubleFBO { read: FBO; write: FBO; swap: () => void; w: number; h: number }

export interface InkFluidOptions {
  simRes: number;
  dyeRes: number;
  iterations: number;
}

export class InkFluid {
  private gl: WebGL2RenderingContext;
  private progs = {} as Record<ProgName, { p: WebGLProgram; u: Record<string, WebGLUniformLocation | null> }>;
  private velocity!: DoubleFBO;
  private dye!: DoubleFBO;
  private pressure!: DoubleFBO;
  private divergenceF!: FBO;
  private curlF!: FBO;
  private ink: [number, number, number] = [0.08, 0.075, 0.07];
  private rim: [number, number, number] = [0.94, 0.3, 0.18];
  strength = 1;
  readonly ok: boolean;

  constructor(private canvas: HTMLCanvasElement, private opts: InkFluidOptions) {
    const gl = canvas.getContext('webgl2', { alpha: true, premultipliedAlpha: true, antialias: false, depth: false, stencil: false, preserveDrawingBuffer: false });
    this.ok = false;
    if (!gl || !gl.getExtension('EXT_color_buffer_float')) {
      this.gl = gl as WebGL2RenderingContext;
      return;
    }
    gl.getExtension('OES_texture_float_linear');
    this.gl = gl;
    try {
      const vs = this.shader(gl.VERTEX_SHADER, BASE_VERT);
      for (const name of Object.keys(SHADERS) as ProgName[]) {
        const p = gl.createProgram()!;
        gl.attachShader(p, vs);
        gl.attachShader(p, this.shader(gl.FRAGMENT_SHADER, SHADERS[name]));
        gl.bindAttribLocation(p, 0, 'aPos');
        gl.linkProgram(p);
        if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p) || name);
        const u: Record<string, WebGLUniformLocation | null> = {};
        const n = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS) as number;
        for (let i = 0; i < n; i++) {
          const info = gl.getActiveUniform(p, i);
          if (info) u[info.name] = gl.getUniformLocation(p, info.name);
        }
        this.progs[name] = { p, u };
      }
      const buf = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, buf);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, -1, 1, 1, 1, 1, -1]), gl.STATIC_DRAW);
      const ibuf = gl.createBuffer();
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ibuf);
      gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array([0, 1, 2, 0, 2, 3]), gl.STATIC_DRAW);
      gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
      gl.enableVertexAttribArray(0);
      this.resize();
      (this as { ok: boolean }).ok = true;
    } catch {
      (this as { ok: boolean }).ok = false;
    }
  }

  private shader(type: number, src: string) {
    const gl = this.gl;
    const s = gl.createShader(type)!;
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) || 'shader');
    return s;
  }

  private fbo(w: number, h: number, internal: number, format: number): FBO {
    const gl = this.gl;
    const tex = gl.createTexture()!;
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texImage2D(gl.TEXTURE_2D, 0, internal, w, h, 0, format, gl.HALF_FLOAT, null);
    const fbo = gl.createFramebuffer()!;
    gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
    gl.viewport(0, 0, w, h);
    gl.clearColor(0, 0, 0, 1);
    gl.clear(gl.COLOR_BUFFER_BIT);
    return { tex, fbo, w, h };
  }

  private double(w: number, h: number, internal: number, format: number): DoubleFBO {
    let a = this.fbo(w, h, internal, format);
    let b = this.fbo(w, h, internal, format);
    const d: DoubleFBO = {
      get read() { return a; },
      get write() { return b; },
      swap() { const t = a; a = b; b = t; },
      w, h,
    } as DoubleFBO;
    return d;
  }

  private dims(res: number) {
    const aspect = this.canvas.width / Math.max(1, this.canvas.height);
    return aspect >= 1
      ? { w: Math.round(res * aspect), h: res }
      : { w: res, h: Math.round(res / aspect) };
  }

  resize() {
    const gl = this.gl;
    const sim = this.dims(this.opts.simRes);
    const dye = this.dims(this.opts.dyeRes);
    this.velocity = this.double(sim.w, sim.h, gl.RG16F, gl.RG);
    this.dye = this.double(dye.w, dye.h, gl.RGBA16F, gl.RGBA);
    this.pressure = this.double(sim.w, sim.h, gl.R16F, gl.RED);
    this.divergenceF = this.fbo(sim.w, sim.h, gl.R16F, gl.RED);
    this.curlF = this.fbo(sim.w, sim.h, gl.R16F, gl.RED);
  }

  setColors(ink: [number, number, number], rim: [number, number, number]) {
    this.ink = ink;
    this.rim = rim;
  }

  private use(name: ProgName) {
    const prog = this.progs[name];
    this.gl.useProgram(prog.p);
    return prog.u;
  }

  private blit(target: FBO | null) {
    const gl = this.gl;
    if (target) {
      gl.viewport(0, 0, target.w, target.h);
      gl.bindFramebuffer(gl.FRAMEBUFFER, target.fbo);
    } else {
      gl.viewport(0, 0, gl.drawingBufferWidth, gl.drawingBufferHeight);
      gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    }
    gl.drawElements(gl.TRIANGLES, 6, gl.UNSIGNED_SHORT, 0);
  }

  private bind(unit: number, tex: WebGLTexture) {
    const gl = this.gl;
    gl.activeTexture(gl.TEXTURE0 + unit);
    gl.bindTexture(gl.TEXTURE_2D, tex);
    return unit;
  }

  /**
   * 在 (x, y)（0–1，左上为原点）注入速度与墨。
   * dx、dy 为像素位移；ink 为墨量，vermilion 为朱砂量；radius 为相对半径。
   */
  splat(x: number, y: number, dx: number, dy: number, ink: number, vermilion = 0, radius = 0.0012) {
    if (!this.ok) return;
    const gl = this.gl;
    const aspect = this.canvas.width / Math.max(1, this.canvas.height);
    let u = this.use('splat');
    gl.uniform1i(u.uTarget, this.bind(0, this.velocity.read.tex));
    gl.uniform1f(u.uAspect, aspect);
    gl.uniform2f(u.uPoint, x, 1 - y);
    gl.uniform3f(u.uColor, dx, -dy, 0);
    gl.uniform1f(u.uRadius, radius * (aspect > 1 ? aspect : 1));
    gl.uniform2f(u.uTexel, 1 / this.velocity.w, 1 / this.velocity.h);
    this.blit(this.velocity.write);
    this.velocity.swap();

    u = this.use('splat');
    gl.uniform1i(u.uTarget, this.bind(0, this.dye.read.tex));
    gl.uniform1f(u.uAspect, aspect);
    gl.uniform2f(u.uPoint, x, 1 - y);
    gl.uniform3f(u.uColor, ink, vermilion, 0);
    gl.uniform1f(u.uRadius, radius * (aspect > 1 ? aspect : 1));
    gl.uniform2f(u.uTexel, 1 / this.dye.w, 1 / this.dye.h);
    this.blit(this.dye.write);
    this.dye.swap();
  }

  step(dtMs: number) {
    if (!this.ok) return;
    const gl = this.gl;
    const dt = Math.min(dtMs, 33) / 1000;
    const k = dt * 60;
    gl.disable(gl.BLEND);
    const vt = [1 / this.velocity.w, 1 / this.velocity.h] as const;

    let u = this.use('curl');
    gl.uniform2f(u.uTexel, ...vt);
    gl.uniform1i(u.uVelocity, this.bind(0, this.velocity.read.tex));
    this.blit(this.curlF);

    u = this.use('vorticity');
    gl.uniform2f(u.uTexel, ...vt);
    gl.uniform1i(u.uVelocity, this.bind(0, this.velocity.read.tex));
    gl.uniform1i(u.uCurl, this.bind(1, this.curlF.tex));
    gl.uniform1f(u.uCurlK, 18);
    gl.uniform1f(u.uDt, dt);
    this.blit(this.velocity.write);
    this.velocity.swap();

    u = this.use('divergence');
    gl.uniform2f(u.uTexel, ...vt);
    gl.uniform1i(u.uVelocity, this.bind(0, this.velocity.read.tex));
    this.blit(this.divergenceF);

    u = this.use('fade');
    gl.uniform2f(u.uTexel, ...vt);
    gl.uniform1i(u.uTex, this.bind(0, this.pressure.read.tex));
    gl.uniform1f(u.uValue, 0.8);
    this.blit(this.pressure.write);
    this.pressure.swap();

    u = this.use('pressure');
    gl.uniform2f(u.uTexel, ...vt);
    gl.uniform1i(u.uDivergence, this.bind(1, this.divergenceF.tex));
    for (let i = 0; i < this.opts.iterations; i++) {
      gl.uniform1i(u.uPressure, this.bind(0, this.pressure.read.tex));
      this.blit(this.pressure.write);
      this.pressure.swap();
    }

    u = this.use('gradient');
    gl.uniform2f(u.uTexel, ...vt);
    gl.uniform1i(u.uPressure, this.bind(0, this.pressure.read.tex));
    gl.uniform1i(u.uVelocity, this.bind(1, this.velocity.read.tex));
    this.blit(this.velocity.write);
    this.velocity.swap();

    u = this.use('advect');
    gl.uniform2f(u.uTexel, ...vt);
    gl.uniform1i(u.uVelocity, this.bind(0, this.velocity.read.tex));
    gl.uniform1i(u.uSource, this.bind(0, this.velocity.read.tex));
    gl.uniform1f(u.uDt, dt);
    gl.uniform1f(u.uDissipation, Math.pow(0.985, k));
    this.blit(this.velocity.write);
    this.velocity.swap();

    u = this.use('advect');
    gl.uniform2f(u.uTexel, ...vt);
    gl.uniform1i(u.uVelocity, this.bind(0, this.velocity.read.tex));
    gl.uniform1i(u.uSource, this.bind(1, this.dye.read.tex));
    gl.uniform1f(u.uDt, dt);
    // 墨散得很慢：半衰期约 9 秒，让一笔墨能停留、沉淀
    gl.uniform1f(u.uDissipation, Math.pow(0.99872, k));
    this.blit(this.dye.write);
    this.dye.swap();
  }

  render() {
    if (!this.ok) return;
    const gl = this.gl;
    const u = this.use('display');
    gl.uniform2f(u.uTexel, 1 / this.dye.w, 1 / this.dye.h);
    gl.uniform1i(u.uDye, this.bind(0, this.dye.read.tex));
    gl.uniform3f(u.uInk, ...this.ink);
    gl.uniform3f(u.uRim, ...this.rim);
    gl.uniform1f(u.uStrength, this.strength);
    gl.clearColor(0, 0, 0, 0);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.clear(gl.COLOR_BUFFER_BIT);
    this.blit(null);
  }

  dispose() {
    this.gl?.getExtension('WEBGL_lose_context')?.loseContext();
  }
}

/** 读取任意 CSS 颜色表达式的 sRGB 值（0–1） */
export function cssColorToRgb(expr: string): [number, number, number] {
  const probe = document.createElement('i');
  probe.style.color = expr;
  probe.style.display = 'none';
  document.body.appendChild(probe);
  const c = getComputedStyle(probe).color;
  probe.remove();
  const ctx = document.createElement('canvas').getContext('2d');
  if (!ctx) return [0, 0, 0];
  ctx.fillStyle = c;
  ctx.fillRect(0, 0, 1, 1);
  const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data;
  return [r / 255, g / 255, b / 255];
}

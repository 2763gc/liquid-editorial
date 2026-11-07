<script setup lang="ts">
import '~/styles/admin.css';
import { ref, computed, nextTick, onMounted, onBeforeUnmount } from 'vue';
import { User, Lock, Eye, EyeOff, ArrowRight, Check, CircleAlert, ShieldCheck, Info } from 'lucide-vue-next';
import { useTheme } from '~/composables/useTheme';
import { acceptAdminSession, apiErrorMessage } from '~/composables/admin/useAdminApi';

definePageMeta({ layout: false });
useHead({ title: '登入编辑部 · Luntrix Admin' });

const route = useRoute();
const router = useRouter();
const siteTheme = useTheme();

// 开发环境只预填用户名；密码永远不写进构建产物
const username = ref(import.meta.dev ? 'admin' : '');
const password = ref('');
const showPassword = ref(false);
const capsLock = ref(false);
const errorMsg = ref('');
const okMsg = ref('');
const state = ref<'idle' | 'loading' | 'done'>('idle');
const cardRef = ref<HTMLFormElement | null>(null);

/* ---- 第二步：两步验证 ---- */
const step = ref<'password' | 'mfa'>('password');
const mfaToken = ref('');
const code = ref('');
const useRecovery = ref(false);
const codeRef = ref<HTMLInputElement | null>(null);

const REASONS: Record<string, string> = {
  idle: '长时间没有操作，已自动退出。',
  expired: '登录已过期，请重新登录。',
  logout: '已安全退出。',
  revoked: '该会话已在其他设备上被退出。',
};
const notice = computed(() => (typeof route.query.reason === 'string' ? REASONS[route.query.reason] || '' : ''));

function focusCode() {
  nextTick(() => codeRef.value?.focus());
}
function toggleRecovery() {
  useRecovery.value = !useRecovery.value;
  code.value = '';
  errorMsg.value = '';
  focusCode();
}
function backToPassword() {
  step.value = 'password';
  mfaToken.value = '';
  code.value = '';
  useRecovery.value = false;
  password.value = '';
  errorMsg.value = '';
}
/** 验证码只留数字，满 6 位自动提交 */
function onCodeInput() {
  if (useRecovery.value) return;
  code.value = code.value.replace(/\D/g, '').slice(0, 6);
  if (code.value.length === 6) login();
}

function enter(target?: string, delay = 420) {
  state.value = 'done';
  const to = target || (typeof route.query.redirect === 'string' && route.query.redirect.startsWith('/admin') ? route.query.redirect : '/admin');
  setTimeout(() => router.replace(to), delay);
}

/** 重新触发抖动动画（不重建表单，保留输入焦点） */
function shake() {
  const el = cardRef.value;
  if (!el) return;
  el.classList.remove('is-shake');
  void el.offsetWidth;
  el.classList.add('is-shake');
}

function onKey(e: KeyboardEvent) {
  if (typeof e.getModifierState === 'function') capsLock.value = e.getModifierState('CapsLock');
}

async function login() {
  if (state.value !== 'idle') return;
  errorMsg.value = '';
  if (step.value === 'mfa') return verifyCode();
  if (!username.value.trim() || !password.value) {
    errorMsg.value = '请输入用户名和密码';
    shake();
    return;
  }
  state.value = 'loading';
  try {
    const data = await $fetch<any>('/api/v1/admin/auth/login', {
      method: 'POST',
      body: { username: username.value.trim(), password: password.value },
    });
    password.value = '';
    if (data.mfa_required) {
      mfaToken.value = data.mfa_token;
      step.value = 'mfa';
      state.value = 'idle';
      focusCode();
      return;
    }
    acceptAdminSession(data);
    enter();
  } catch (err: any) {
    state.value = 'idle';
    errorMsg.value = err?.status ? apiErrorMessage(err, '登录失败，请检查账号密码') : '网络请求失败，请稍后重试';
    shake();
  }
}

async function verifyCode() {
  const value = code.value.trim();
  if (useRecovery.value ? value.replace(/[^a-z0-9]/gi, '').length !== 10 : value.length !== 6) {
    errorMsg.value = useRecovery.value ? '恢复码是 10 位字母数字' : '请输入 6 位验证码';
    shake();
    return;
  }
  state.value = 'loading';
  try {
    const data = await $fetch<any>('/api/v1/admin/auth/login/mfa', {
      method: 'POST',
      body: { mfa_token: mfaToken.value, code: value },
    });
    acceptAdminSession(data);
    if (typeof data.recovery_codes_remaining === 'number') {
      okMsg.value = `已用掉一个恢复码，还剩 ${data.recovery_codes_remaining} 个。进入后台后请尽快在「安全」里重新生成。`;
      enter(undefined, 2200);
    } else enter();
  } catch (err: any) {
    state.value = 'idle';
    code.value = '';
    // 临时凭证过期或次数用完：回到第一步重新输入密码
    if (err?.status === 401) {
      backToPassword();
      errorMsg.value = apiErrorMessage(err, '验证超时，请重新输入密码');
    } else {
      errorMsg.value = err?.status ? apiErrorMessage(err, '验证码不正确') : '网络请求失败，请稍后重试';
      focusCode();
    }
    shake();
  }
}

onMounted(() => {
  let t: 'light' | 'dark' = 'dark';
  try { t = localStorage.getItem('blog_admin_theme') === 'light' ? 'light' : 'dark'; } catch {}
  siteTheme.setOverride(t);
});
// 回前台时还原访客的主题偏好；进入后台由后台布局接管
onBeforeUnmount(() => {
  if (!router.currentRoute.value.path.startsWith('/admin')) siteTheme.setOverride(null);
});
</script>

<template>
  <div class="login">
    <!-- 品牌面板 -->
    <aside class="brand" aria-hidden="true" data-cursor="drag">
      <InkPond class="brand-pond" tone="dark" :seed="11" />
      <div class="brand-top">
        <span class="brand-mark" />
        <span>Liquid Editorial</span>
        <span class="brand-sep" />
        <span>Vol. {{ new Date().getFullYear() }}</span>
      </div>
      <div class="brand-word">
        <span class="brand-line"><span>The</span></span>
        <span class="brand-line"><em>Editorial</em></span>
        <span class="brand-line"><span>Desk.</span></span>
      </div>
      <p class="brand-foot">写作、校对、排版与发布——一份个人刊物的全部后台工序。</p>
    </aside>

    <!-- 表单 -->
    <main class="panel">
      <form ref="cardRef" class="card" novalidate @submit.prevent="login" @keydown="onKey" @keyup="onKey">
        <p class="card-eyebrow"><span>Admin</span> 编辑部后台<template v-if="step === 'mfa'"> · 第二步</template></p>
        <h1 class="card-title">{{ step === 'mfa' ? '再验一道' : '登入编辑部' }}</h1>
        <p class="card-sub">{{ step === 'mfa' ? '密码无误。再输入一次性验证码，确认是你本人。' : '欢迎回来。今天想写点什么？' }}</p>

        <Transition name="err">
          <p v-if="errorMsg" class="card-err" role="alert"><CircleAlert :size="15" />{{ errorMsg }}</p>
          <p v-else-if="okMsg" class="card-note is-ok" role="status"><Check :size="15" />{{ okMsg }}</p>
          <p v-else-if="notice && step === 'password'" class="card-note" role="status"><Info :size="15" />{{ notice }}</p>
        </Transition>

        <template v-if="step === 'mfa'">
          <div class="a-field">
            <label class="a-label" for="lg-code">{{ useRecovery ? '恢复码' : '两步验证码' }}</label>
            <label class="a-input-icon">
              <ShieldCheck :size="15" :stroke-width="1.75" />
              <input
                id="lg-code"
                ref="codeRef"
                v-model="code"
                class="a-input field code"
                :class="{ 'is-recovery': useRecovery }"
                type="text"
                :inputmode="useRecovery ? 'text' : 'numeric'"
                :autocomplete="useRecovery ? 'off' : 'one-time-code'"
                :maxlength="useRecovery ? 11 : 6"
                :placeholder="useRecovery ? 'xxxxx-xxxxx' : '000000'"
                autocapitalize="off"
                spellcheck="false"
                @input="onCodeInput"
              >
            </label>
            <p class="hint">{{ useRecovery ? '每个恢复码只能用一次。' : '打开身份验证器，输入「Liquid Editorial」下的 6 位数字。' }}</p>
          </div>
          <div class="mfa-links">
            <button type="button" class="link" @click="toggleRecovery">{{ useRecovery ? '改用验证码' : '手机不在身边？用恢复码' }}</button>
            <button type="button" class="link" @click="backToPassword">返回上一步</button>
          </div>
        </template>

        <template v-else>
        <div class="a-field">
          <label class="a-label" for="lg-user">用户名</label>
          <label class="a-input-icon">
            <User :size="15" :stroke-width="1.75" />
            <input id="lg-user" v-model="username" class="a-input field" type="text" autocomplete="username" autocapitalize="off" spellcheck="false" required>
          </label>
        </div>

        <div class="a-field">
          <label class="a-label" for="lg-pass">密码</label>
          <label class="a-input-icon">
            <Lock :size="15" :stroke-width="1.75" />
            <input id="lg-pass" v-model="password" class="a-input field has-toggle" :type="showPassword ? 'text' : 'password'" autocomplete="current-password" required>
            <button type="button" class="eye" :aria-label="showPassword ? '隐藏密码' : '显示密码'" @click="showPassword = !showPassword">
              <EyeOff v-if="showPassword" :size="15" /><Eye v-else :size="15" />
            </button>
          </label>
          <Transition name="err">
            <p v-if="capsLock" class="caps">大写锁定已开启</p>
          </Transition>
        </div>
        </template>

        <button type="submit" class="a-btn a-btn-lg a-btn-primary submit" :class="`is-${state}`" :disabled="state !== 'idle'">
          <Transition name="swap" mode="out-in">
            <span v-if="state === 'loading'" key="l" class="submit-inner"><span class="a-spin" /> 验证中</span>
            <span v-else-if="state === 'done'" key="d" class="submit-inner"><Check :size="16" :stroke-width="2.5" /> 欢迎回来</span>
            <span v-else-if="step === 'mfa'" key="m" class="submit-inner">验证并进入 <ArrowRight :size="15" :stroke-width="2" class="submit-arrow" /></span>
            <span v-else key="i" class="submit-inner">进入控制台 <ArrowRight :size="15" :stroke-width="2" class="submit-arrow" /></span>
          </Transition>
        </button>

        <p class="card-foot">
          连续 5 次失败将锁定 15 分钟 · <NuxtLink to="/" class="back">返回前台</NuxtLink>
        </p>
      </form>
    </main>
  </div>
</template>

<style scoped>
.login {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(400px, 1fr);
  min-height: 100vh;
  min-height: 100dvh;
  font-family: var(--font-sans);
  color: var(--color-ink);
  background: var(--color-bg);
}

/* ---------------- 品牌面板（始终是墨色） ---------------- */
.brand {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: clamp(28px, 4vw, 56px);
  overflow: hidden;
  color: var(--night-ink);
  background: var(--night-bg);
}
.brand-pond { z-index: 0; }
.brand > :not(.brand-pond) { position: relative; z-index: 1; pointer-events: none; }
.brand-top {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: rgb(236 232 223 / 0.5);
}
.brand-mark { width: 10px; height: 10px; background: var(--color-accent); }
.brand-sep { width: 28px; height: 1px; background: rgb(236 232 223 / 0.2); }
.brand-word {
  position: relative;
  display: flex;
  flex-direction: column;
  font-family: var(--font-display);
  font-size: clamp(56px, 8.4vw, 140px);
  font-weight: 800;
  line-height: 0.9;
  letter-spacing: -0.05em;
  font-variation-settings: "opsz" 144, "SOFT" 30;
}
.brand-line { display: block; overflow: hidden; padding: 0 0.12em 0.08em 0; }
.brand-line > * { display: block; animation: line-rise 1300ms var(--ease-out-expo) backwards; }
.brand-line:nth-child(1) > * { animation-delay: 80ms; }
.brand-line:nth-child(2) > * { animation-delay: 170ms; }
.brand-line:nth-child(3) > * { animation-delay: 260ms; }
.brand-word em { font-style: italic; font-weight: 300; color: var(--color-accent); font-variation-settings: "opsz" 144, "SOFT" 100, "WONK" 1; }
@keyframes line-rise { from { transform: translate3d(0, 105%, 0) rotate(3deg); } }
.brand-foot { position: relative; max-width: 26em; font-family: var(--font-serif); font-size: 15px; line-height: 1.8; color: rgb(236 232 223 / 0.55); }

/* ---------------- 表单 ---------------- */
.panel { display: grid; place-items: center; padding: 32px 24px; }
.card {
  width: min(380px, 100%);
  display: flex;
  flex-direction: column;
  gap: 18px;
  animation: card-in 900ms var(--ease-out-expo) 120ms backwards;
}
@keyframes card-in { from { opacity: 0; transform: translate3d(0, 16px, 0); filter: blur(4px); } }
.card.is-shake { animation: shake 520ms var(--ease-out-quart); }
@keyframes shake {
  15% { transform: translateX(-8px); }
  30% { transform: translateX(7px); }
  45% { transform: translateX(-5px); }
  60% { transform: translateX(4px); }
  75% { transform: translateX(-2px); }
}
.card-eyebrow { display: flex; gap: 10px; font-family: var(--font-mono); font-size: 10.5px; letter-spacing: 0.16em; text-transform: uppercase; color: var(--color-ink-faint); }
.card-eyebrow span { color: var(--color-accent); }
.card-title { margin-top: -6px; font-family: var(--font-serif); font-size: 32px; font-weight: 900; letter-spacing: -0.02em; }
.card-sub { margin-top: -10px; margin-bottom: 6px; font-size: 14px; color: var(--color-ink-muted); }
.card-err {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  font-size: 13px;
  color: var(--a-danger);
  background: color-mix(in oklab, var(--a-danger) 10%, transparent);
  border: 1px solid color-mix(in oklab, var(--a-danger) 25%, transparent);
  border-radius: var(--a-radius);
}
.card-note {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-ink-muted);
  background: var(--color-surface);
  border: 1px solid var(--color-line);
  border-radius: var(--a-radius);
}
.card-note > svg { flex-shrink: 0; margin-top: 3px; }
.card-note.is-ok { color: var(--a-ok); border-color: color-mix(in oklab, var(--a-ok) 30%, transparent); background: color-mix(in oklab, var(--a-ok) 8%, transparent); }
.field { height: 44px; font-size: 14.5px; }
/* 验证码：等宽、加大字距，一眼数清位数 */
.code { font-family: var(--font-mono); font-size: 20px; letter-spacing: 0.42em; font-variant-numeric: tabular-nums; }
.code.is-recovery { font-size: 16px; letter-spacing: 0.16em; }
.code::placeholder { color: var(--color-ink-faint); opacity: 0.5; }
.hint { margin-top: 6px; font-size: 12px; color: var(--color-ink-faint); }
.mfa-links { display: flex; justify-content: space-between; margin-top: -6px; }
.link {
  font-size: 12.5px;
  color: var(--color-ink-muted);
  text-decoration: underline;
  text-underline-offset: 3px;
  text-decoration-color: var(--color-line-strong);
  transition: color 160ms ease;
}
.link:hover { color: var(--color-ink); }
.has-toggle { padding-right: 40px; }
.eye {
  position: absolute;
  right: 6px;
  top: 50%;
  transform: translateY(-50%);
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: var(--a-radius-sm);
  color: var(--color-ink-faint);
  transition: color 160ms ease, background-color 160ms ease;
}
.eye:hover { color: var(--color-ink); background: var(--a-hover); }
.caps { font-size: 12px; color: var(--a-warn); }
.submit { height: 46px; margin-top: 6px; font-size: 14px; }
.submit.is-done { background: var(--a-ok); border-color: var(--a-ok); color: var(--day-bg); }
.submit[disabled] { opacity: 1; }
.submit-inner { display: inline-flex; align-items: center; gap: 8px; }
.submit-arrow { transition: transform 500ms var(--ease-out-expo); }
.submit:hover .submit-arrow { transform: translateX(4px); }
.card-foot { font-size: 12px; text-align: center; color: var(--color-ink-faint); }
.back { color: var(--color-ink-muted); text-decoration: underline; text-underline-offset: 3px; text-decoration-color: var(--color-line-strong); }
.back:hover { color: var(--color-ink); }

.err-enter-active { transition: opacity 260ms ease, transform 420ms var(--ease-spring); }
.err-leave-active { transition: opacity 160ms ease; }
.err-enter-from { opacity: 0; transform: translateY(-6px); }
.err-leave-to { opacity: 0; }
.swap-enter-active, .swap-leave-active { transition: opacity 180ms ease, transform 320ms var(--ease-out-expo); }
.swap-enter-from { opacity: 0; transform: translateY(8px); }
.swap-leave-to { opacity: 0; transform: translateY(-8px); }

@media (max-width: 860px) {
  .login { grid-template-columns: 1fr; grid-template-rows: auto 1fr; }
  .brand { min-height: 240px; }
  .brand-word { font-size: clamp(48px, 14vw, 80px); }
  .brand-foot { display: none; }
}
</style>

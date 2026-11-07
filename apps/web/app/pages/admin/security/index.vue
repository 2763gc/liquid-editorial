<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue';
import { ShieldCheck, ShieldOff, KeyRound, MonitorSmartphone, ScrollText, Copy, Download, RefreshCw, LogOut, Check, X } from 'lucide-vue-next';
import { adminFetch, apiErrorMessage, adminUser } from '~/composables/admin/useAdminApi';
import { useToast } from '~/composables/admin/useToast';
import { useConfirm } from '~/composables/admin/useConfirm';
import { timeAgo } from '~/utils/format';

/**
 * § 06 安全
 * - 两步验证：输入密码 → 本地生成二维码（密钥不经过任何第三方）→ 输入一次验证码确认 → 恢复码只显示这一次
 * - 修改密码：与服务端同一套规则实时校验；改密后其他设备全部退出
 * - 登录会话：每台设备一行，可单独踢出
 * - 操作留痕：登录、会话、安全设置与内容写操作，按级别筛选
 */
definePageMeta({ layout: 'admin' });
useHead({ title: '安全 · 编辑部后台' });

const toast = useToast();
const { confirm } = useConfirm();

interface Overview {
  mfa_enabled: boolean;
  mfa_enabled_at: string | null;
  mfa_setup_pending: boolean;
  recovery_codes_remaining: number;
  password_changed_at: string | null;
  last_login_at: string | null;
  sessions_active: number;
  failed_attempts_24h: number;
  session_mfa: boolean;
  policy: {
    access_token_minutes: number;
    session_idle_days: number;
    session_absolute_days: number;
    lockout: { window_minutes: number; per_ip: number; per_account: number };
  };
}
interface Session { id: string; current: boolean; device: string; user_agent: string | null; ip_masked: string | null; created_at: string; last_used_at: string; expires_at: string; mfa: boolean }
interface AuditItem { id: number; at: string; actor: string | null; action: string; level: 'info' | 'warn' | 'danger'; target: string | null; ip_masked: string | null; device: string | null; detail: Record<string, unknown> | null }

const overview = ref<Overview | null>(null);
const sessions = ref<Session[]>([]);
const loading = ref(true);

async function loadOverview() {
  overview.value = await adminFetch<Overview>('/api/v1/admin/auth/security');
}
async function loadSessions() {
  sessions.value = (await adminFetch<{ items: Session[] }>('/api/v1/admin/auth/sessions')).items;
}

function fullTime(iso?: string | null) {
  if (!iso) return '';
  return new Date(iso).toLocaleString('zh-CN', { hour12: false });
}

/* ---------------------------------------------------------------- 两步验证 */
type MfaStep = 'idle' | 'password' | 'scan' | 'codes';
const mfaStep = ref<MfaStep>('idle');
const mfaBusy = ref(false);
const setupPassword = ref('');
const setupSecret = ref('');
const setupUri = ref('');
const setupCode = ref('');
const qr = ref<{ n: number; d: string } | null>(null);
const recoveryCodes = ref<string[]>([]);
const codesSaved = ref(false);
const pwInput = ref<HTMLInputElement | null>(null);
const codeInput = ref<HTMLInputElement | null>(null);

const groupedSecret = computed(() => (setupSecret.value.match(/.{1,4}/g) || []).join(' '));

function startSetup() {
  mfaStep.value = 'password';
  setupPassword.value = '';
  nextTick(() => pwInput.value?.focus());
}
function cancelSetup() {
  mfaStep.value = 'idle';
  setupPassword.value = '';
  setupSecret.value = '';
  setupCode.value = '';
  qr.value = null;
}

/** 二维码在本地生成：otpauth 链接里的密钥不经过任何第三方服务 */
async function buildQr(text: string) {
  const { default: qrcode } = await import('qrcode-generator');
  const code = qrcode(0, 'M');
  code.addData(text);
  code.make();
  const n = code.getModuleCount();
  let d = '';
  for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (code.isDark(r, c)) d += `M${c} ${r}h1v1h-1z`;
  qr.value = { n, d };
}

async function generateSecret() {
  if (!setupPassword.value || mfaBusy.value) return;
  mfaBusy.value = true;
  try {
    const d = await adminFetch<{ secret: string; otpauth_uri: string }>('/api/v1/admin/auth/totp/setup', { method: 'POST', body: { password: setupPassword.value } });
    setupPassword.value = '';
    setupSecret.value = d.secret;
    setupUri.value = d.otpauth_uri;
    await buildQr(d.otpauth_uri);
    mfaStep.value = 'scan';
    nextTick(() => codeInput.value?.focus());
  } catch (err) {
    toast.error('无法生成密钥', apiErrorMessage(err));
  } finally {
    mfaBusy.value = false;
  }
}

function onSetupCode() {
  setupCode.value = setupCode.value.replace(/\D/g, '').slice(0, 6);
  if (setupCode.value.length === 6) enableMfa();
}

async function enableMfa() {
  if (setupCode.value.length !== 6 || mfaBusy.value) return;
  mfaBusy.value = true;
  try {
    const d = await adminFetch<{ recovery_codes: string[]; revoked: number }>('/api/v1/admin/auth/totp/enable', { method: 'POST', body: { code: setupCode.value } });
    recoveryCodes.value = d.recovery_codes;
    codesSaved.value = false;
    setupSecret.value = '';
    qr.value = null;
    mfaStep.value = 'codes';
    if (adminUser.value) adminUser.value = { ...adminUser.value, mfa_enabled: true };
    toast.success('两步验证已启用', d.revoked ? `其他 ${d.revoked} 个会话已退出，需要重新登录` : '下次登录时需要输入验证码');
    await Promise.all([loadOverview(), loadSessions()]);
  } catch (err) {
    setupCode.value = '';
    toast.error('启用失败', apiErrorMessage(err));
    nextTick(() => codeInput.value?.focus());
  } finally {
    mfaBusy.value = false;
  }
}

function codesText() {
  return [
    'Liquid Editorial · 两步验证恢复码',
    `账号：${adminUser.value?.username || ''}`,
    `生成于：${fullTime(new Date().toISOString())}`,
    '每个恢复码只能使用一次。请离线保存，不要截图发到聊天软件里。',
    '',
    ...recoveryCodes.value,
    '',
  ].join('\n');
}
async function copyCodes() {
  try {
    await navigator.clipboard.writeText(codesText());
    toast.success('已复制', '请粘贴到密码管理器里保存');
  } catch {
    toast.error('复制失败', '请手动选择文本复制');
  }
}
function downloadCodes() {
  const url = URL.createObjectURL(new Blob([codesText()], { type: 'text/plain;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = 'liquid-editorial-recovery-codes.txt';
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function finishCodes() {
  recoveryCodes.value = [];
  mfaStep.value = 'idle';
}

/* ---- 已启用：停用 / 重新生成恢复码，都要先复核密码与验证码 ---- */
const reauth = ref<null | 'disable' | 'regen'>(null);
const reauthPassword = ref('');
const reauthCode = ref('');
const reauthInput = ref<HTMLInputElement | null>(null);
function openReauth(kind: 'disable' | 'regen') {
  reauth.value = kind;
  reauthPassword.value = '';
  reauthCode.value = '';
  nextTick(() => reauthInput.value?.focus());
}
async function submitReauth() {
  if (!reauth.value || !reauthPassword.value || !reauthCode.value || mfaBusy.value) return;
  const kind = reauth.value;
  if (kind === 'disable') {
    const ok = await confirm({ title: '停用两步验证？', message: '停用后只凭密码即可登录。除非要更换手机，否则不建议停用。', confirmText: '停用', danger: true });
    if (!ok) return;
  }
  mfaBusy.value = true;
  try {
    const body = { password: reauthPassword.value, code: reauthCode.value.trim() };
    if (kind === 'disable') {
      await adminFetch('/api/v1/admin/auth/totp/disable', { method: 'POST', body });
      if (adminUser.value) adminUser.value = { ...adminUser.value, mfa_enabled: false };
      toast.info('两步验证已停用');
    } else {
      const d = await adminFetch<{ recovery_codes: string[] }>('/api/v1/admin/auth/recovery-codes', { method: 'POST', body });
      recoveryCodes.value = d.recovery_codes;
      codesSaved.value = false;
      mfaStep.value = 'codes';
      toast.success('已生成新的恢复码', '旧的恢复码全部作废');
    }
    reauth.value = null;
    await loadOverview();
  } catch (err) {
    toast.error(kind === 'disable' ? '停用失败' : '生成失败', apiErrorMessage(err));
  } finally {
    reauthPassword.value = '';
    reauthCode.value = '';
    mfaBusy.value = false;
  }
}

/* ---------------------------------------------------------------- 修改密码 */
const pw = ref({ current: '', next: '', confirm: '', code: '' });
const pwBusy = ref(false);
const pwShow = ref(false);
const pwClasses = computed(() => [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter((r) => r.test(pw.value.next)).length);
const pwRules = computed(() => {
  const p = pw.value.next;
  const u = adminUser.value?.username || '';
  return [
    { ok: p.length >= 12, label: '至少 12 个字符' },
    { ok: p.length >= 16 || pwClasses.value >= 3, label: '不足 16 位时，含大写 / 小写 / 数字 / 符号中的三类' },
    { ok: !!p && !(u.length >= 3 && p.toLowerCase().includes(u.toLowerCase())), label: '不含用户名' },
  ];
});
const pwScore = computed(() => {
  const p = pw.value.next;
  if (!p) return 0;
  let s = 0;
  if (p.length >= 12) s++;
  if (p.length >= 16) s++;
  if (pwClasses.value >= 3) s++;
  if (p.length >= 20 || (pwClasses.value === 4 && p.length >= 14)) s++;
  if (!pwRules.value.every((r) => r.ok)) s = Math.min(s, 1);
  return Math.max(1, s);
});
const PW_LABELS = ['', '弱', '尚可', '良好', '坚固'];
const pwMismatch = computed(() => !!pw.value.confirm && pw.value.confirm !== pw.value.next);
const pwReady = computed(() =>
  !!pw.value.current && pwRules.value.every((r) => r.ok) && pw.value.next === pw.value.confirm && (!overview.value?.mfa_enabled || pw.value.code.trim().length >= 6),
);

async function changePassword() {
  if (!pwReady.value || pwBusy.value) return;
  pwBusy.value = true;
  try {
    const d = await adminFetch<{ revoked: number }>('/api/v1/admin/auth/password', {
      method: 'POST',
      body: { current_password: pw.value.current, new_password: pw.value.next, code: pw.value.code.trim() || null },
    });
    pw.value = { current: '', next: '', confirm: '', code: '' };
    toast.success('密码已更新', d.revoked ? `其他 ${d.revoked} 个会话已退出` : '当前会话保持登录');
    await Promise.all([loadOverview(), loadSessions()]);
  } catch (err) {
    toast.error('密码未更新', apiErrorMessage(err));
  } finally {
    pwBusy.value = false;
  }
}

/* ---------------------------------------------------------------- 会话 */
async function revokeSession(s: Session) {
  const ok = await confirm({ title: `退出「${s.device}」？`, message: `${s.ip_masked || '未知网络'} · 最近活动 ${timeAgo(s.last_used_at)}。该设备需要重新登录。`, confirmText: '退出该设备', danger: true });
  if (!ok) return;
  try {
    await adminFetch(`/api/v1/admin/auth/sessions/${encodeURIComponent(s.id)}`, { method: 'DELETE' });
    sessions.value = sessions.value.filter((x) => x.id !== s.id);
    toast.success('已退出该设备');
    loadOverview();
  } catch (err) {
    toast.error('操作失败', apiErrorMessage(err));
  }
}
async function revokeOthers() {
  const others = sessions.value.filter((s) => !s.current).length;
  if (!others) {
    toast.info('没有其他设备在登录');
    return;
  }
  const ok = await confirm({ title: `退出其他 ${others} 个设备？`, message: '只保留当前这台浏览器的登录。', confirmText: '全部退出', danger: true });
  if (!ok) return;
  try {
    const d = await adminFetch<{ revoked: number }>('/api/v1/admin/auth/sessions/revoke-others', { method: 'POST' });
    toast.success(`已退出 ${d.revoked} 个设备`);
    await Promise.all([loadOverview(), loadSessions()]);
  } catch (err) {
    toast.error('操作失败', apiErrorMessage(err));
  }
}

/* ---------------------------------------------------------------- 操作留痕 */
const LEVELS = [
  { key: '', label: '全部' },
  { key: 'warn', label: '注意' },
  { key: 'danger', label: '危险' },
] as const;
const ACTION_LABELS: Record<string, string> = {
  'auth.login': '登录',
  'auth.login_failed': '登录失败',
  'auth.logout': '退出登录',
  'auth.logout_all': '退出全部设备',
  'auth.refresh_reuse': '刷新凭据被重复使用',
  'auth.session_revoked': '踢出一个会话',
  'auth.sessions_revoked': '退出其他会话',
  'auth.password_changed': '修改密码',
  'auth.reauth_failed': '身份复核失败',
  'auth.mfa_enabled': '启用两步验证',
  'auth.mfa_disabled': '停用两步验证',
  'auth.recovery_code_used': '使用恢复码',
  'auth.recovery_codes_regenerated': '重新生成恢复码',
  'post.create': '新建特稿',
  'post.update': '修改特稿',
  'post.publish': '发布 / 撤回特稿',
  'post.delete': '删除特稿',
  'settings.update': '修改站点设置',
  'til.create': '新建今日所学',
  'til.update': '修改今日所学',
  'til.delete': '删除今日所学',
  'link.create': '新增友链',
  'link.update': '修改友链',
  'link.delete': '删除友链',
  'media.upload': '上传媒体',
  'media.delete': '删除媒体',
};
const audit = ref<AuditItem[]>([]);
const auditTotal = ref(0);
const auditPage = ref(1);
const auditLevel = ref<'' | 'warn' | 'danger'>('');
const auditLoading = ref(false);

function actionLabel(a: AuditItem) {
  return ACTION_LABELS[a.action] || a.action;
}
function actionNote(a: AuditItem) {
  const d = a.detail || {};
  const notes: string[] = [];
  if (a.action === 'auth.login_failed') notes.push(d.stage === 'mfa' ? '验证码错误' : '密码错误');
  if (a.action === 'auth.login' && d.mfa) notes.push('两步验证');
  if (typeof d.sessions === 'number' && d.sessions) notes.push(`${d.sessions} 个会话`);
  if (typeof d.sessions_revoked === 'number' && d.sessions_revoked) notes.push(`退出 ${d.sessions_revoked} 个会话`);
  if (typeof d.remaining === 'number') notes.push(`剩余 ${d.remaining} 个`);
  if (d.factor) notes.push(d.factor === 'totp' ? '验证码' : '密码');
  return notes.join(' · ');
}

async function loadAudit(reset = true) {
  auditLoading.value = true;
  try {
    const page = reset ? 1 : auditPage.value + 1;
    const d = await adminFetch<{ items: AuditItem[]; total: number }>('/api/v1/admin/auth/audit', {
      query: { page, page_size: 30, ...(auditLevel.value ? { level: auditLevel.value } : {}) },
    });
    audit.value = reset ? d.items : [...audit.value, ...d.items];
    auditTotal.value = d.total;
    auditPage.value = page;
  } catch (err) {
    toast.error('操作留痕加载失败', apiErrorMessage(err));
  } finally {
    auditLoading.value = false;
  }
}
function setLevel(level: '' | 'warn' | 'danger') {
  if (auditLevel.value === level) return;
  auditLevel.value = level;
  loadAudit(true);
}

onMounted(async () => {
  try {
    await Promise.all([loadOverview(), loadSessions(), loadAudit(true)]);
  } catch (err) {
    toast.error('安全信息加载失败', apiErrorMessage(err));
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="sec">
    <AdminPageHeader index="06" en="Security" title="安全" description="登录凭据只在这台浏览器的内存里；刷新令牌每用一次就换新，被人重复使用会立刻作废整个会话。">
      <button type="button" class="a-btn" @click="revokeOthers"><LogOut :size="14" :stroke-width="1.75" /> 退出其他设备</button>
    </AdminPageHeader>

    <!-- 概览：发丝线分隔的数字栏 -->
    <section class="a-card figs a-rise" style="--i: 1" aria-label="安全概览">
      <div class="fig">
        <p class="fig-label">两步验证</p>
        <p class="fig-value">
          <span class="a-status" :class="overview?.mfa_enabled ? 'is-ok' : 'is-warn'">{{ overview ? (overview.mfa_enabled ? '已启用' : '未启用') : '—' }}</span>
        </p>
        <p class="fig-sub a-faint">{{ overview?.mfa_enabled_at ? `启用于 ${timeAgo(overview.mfa_enabled_at)}` : '强烈建议启用' }}</p>
      </div>
      <div class="fig">
        <p class="fig-label">恢复码</p>
        <p class="fig-value num">{{ overview?.mfa_enabled ? overview.recovery_codes_remaining : '—' }}</p>
        <p class="fig-sub a-faint" :class="{ 'is-warn': overview?.mfa_enabled && overview.recovery_codes_remaining <= 3 }">
          {{ overview?.mfa_enabled ? (overview.recovery_codes_remaining <= 3 ? '所剩不多，尽快重新生成' : '每个只能用一次') : '启用两步验证后生成' }}
        </p>
      </div>
      <div class="fig">
        <p class="fig-label">活跃会话</p>
        <p class="fig-value num">{{ overview?.sessions_active ?? '—' }}</p>
        <p class="fig-sub a-faint">{{ overview?.last_login_at ? `本次登录 ${timeAgo(overview.last_login_at)}` : '' }}</p>
      </div>
      <div class="fig">
        <p class="fig-label">24 小时失败登录</p>
        <p class="fig-value num" :class="{ 'is-alert': (overview?.failed_attempts_24h || 0) > 0 }">{{ overview?.failed_attempts_24h ?? '—' }}</p>
        <p class="fig-sub a-faint">{{ (overview?.failed_attempts_24h || 0) > 0 ? '详情见下方操作留痕' : '风平浪静' }}</p>
      </div>
      <div class="fig">
        <p class="fig-label">上次改密</p>
        <p class="fig-value fig-text">{{ overview?.password_changed_at ? timeAgo(overview.password_changed_at) : '从未' }}</p>
        <p class="fig-sub a-faint">{{ overview?.password_changed_at ? fullTime(overview.password_changed_at) : '默认密码请立即更换' }}</p>
      </div>
    </section>

    <section class="grid">
      <div class="stack span-7">
        <!-- 两步验证 -->
        <div class="a-card a-rise" style="--i: 2">
          <header class="a-card-head">
            <div>
              <p class="a-card-title" data-no="A">两步验证</p>
              <p class="a-card-sub">密码之外再加一道：手机上的身份验证器每 30 秒生成一次 6 位数字</p>
            </div>
            <ShieldCheck v-if="overview?.mfa_enabled" :size="18" :stroke-width="1.5" class="head-icon is-ok" />
            <ShieldOff v-else :size="18" :stroke-width="1.5" class="head-icon" />
          </header>

          <div class="a-card-body">
            <!-- 恢复码：只显示这一次 -->
            <div v-if="mfaStep === 'codes'" class="codes">
              <p class="step-title">保存恢复码</p>
              <p class="a-muted step-desc">手机丢了或换了，用它们代替验证码登录。<b>每个只能用一次，离开此页后不会再显示。</b></p>
              <ol class="code-grid">
                <li v-for="(c, i) in recoveryCodes" :key="c" :style="{ '--n': i }"><span class="code-no">{{ String(i + 1).padStart(2, '0') }}</span>{{ c }}</li>
              </ol>
              <div class="row">
                <button type="button" class="a-btn" @click="copyCodes"><Copy :size="14" :stroke-width="1.75" /> 复制</button>
                <button type="button" class="a-btn" @click="downloadCodes"><Download :size="14" :stroke-width="1.75" /> 下载 .txt</button>
              </div>
              <label class="ack"><input v-model="codesSaved" type="checkbox"> 我已把恢复码存在安全的地方</label>
              <button type="button" class="a-btn a-btn-primary" :disabled="!codesSaved" @click="finishCodes">完成</button>
            </div>

            <!-- 未启用 -->
            <template v-else-if="!overview?.mfa_enabled">
              <div v-if="mfaStep === 'idle'" class="intro">
                <ol class="howto">
                  <li><b>01</b>在手机上装一个身份验证器（1Password、Authy、Google Authenticator、微软验证器都行）</li>
                  <li><b>02</b>扫描这里生成的二维码</li>
                  <li><b>03</b>输入 App 显示的 6 位数字，并保存恢复码</li>
                </ol>
                <button type="button" class="a-btn a-btn-primary" :disabled="loading" @click="startSetup"><ShieldCheck :size="14" :stroke-width="1.75" /> 启用两步验证</button>
              </div>

              <form v-else-if="mfaStep === 'password'" class="inline-form" @submit.prevent="generateSecret">
                <p class="step-title">先确认是你本人</p>
                <div class="a-field">
                  <label class="a-label" for="mfa-pw">当前密码</label>
                  <input id="mfa-pw" ref="pwInput" v-model="setupPassword" class="a-input" type="password" autocomplete="current-password">
                </div>
                <div class="row">
                  <button type="submit" class="a-btn a-btn-primary" :disabled="!setupPassword || mfaBusy"><span v-if="mfaBusy" class="a-spin" />生成密钥</button>
                  <button type="button" class="a-btn a-btn-quiet" @click="cancelSetup">取消</button>
                </div>
              </form>

              <div v-else-if="mfaStep === 'scan'" class="scan">
                <figure class="qr" aria-label="两步验证二维码">
                  <svg v-if="qr" :viewBox="`-3 -3 ${qr.n + 6} ${qr.n + 6}`" shape-rendering="crispEdges" role="img" aria-label="用身份验证器扫描">
                    <rect :x="-3" :y="-3" :width="qr.n + 6" :height="qr.n + 6" fill="#fbf9f4" />
                    <path :d="qr.d" fill="#16130f" />
                  </svg>
                  <figcaption>用身份验证器扫描</figcaption>
                </figure>
                <form class="inline-form" @submit.prevent="enableMfa">
                  <p class="step-title">扫码，然后输入 6 位数字</p>
                  <p class="a-muted step-desc">扫不了？在 App 里选「手动输入密钥」：</p>
                  <p class="secret" :title="setupSecret">{{ groupedSecret }}</p>
                  <div class="a-field">
                    <label class="a-label" for="mfa-code">验证码</label>
                    <input
                      id="mfa-code"
                      ref="codeInput"
                      v-model="setupCode"
                      class="a-input otp"
                      type="text"
                      inputmode="numeric"
                      autocomplete="one-time-code"
                      maxlength="6"
                      placeholder="000000"
                      @input="onSetupCode"
                    >
                  </div>
                  <div class="row">
                    <button type="submit" class="a-btn a-btn-primary" :disabled="setupCode.length !== 6 || mfaBusy"><span v-if="mfaBusy" class="a-spin" />确认启用</button>
                    <button type="button" class="a-btn a-btn-quiet" @click="cancelSetup">取消</button>
                  </div>
                </form>
              </div>
            </template>

            <!-- 已启用 -->
            <template v-else>
              <dl class="facts">
                <div><dt>状态</dt><dd><span class="a-status is-ok">已启用</span></dd></div>
                <div><dt>启用于</dt><dd :title="fullTime(overview.mfa_enabled_at)">{{ timeAgo(overview.mfa_enabled_at) }}</dd></div>
                <div><dt>恢复码</dt><dd>剩余 {{ overview.recovery_codes_remaining }} 个</dd></div>
                <div><dt>本次会话</dt><dd>{{ overview.session_mfa ? '经过两步验证' : '启用前建立' }}</dd></div>
              </dl>
              <form v-if="reauth" class="inline-form reauth" @submit.prevent="submitReauth">
                <p class="step-title">{{ reauth === 'disable' ? '停用两步验证' : '重新生成恢复码' }} · 复核身份</p>
                <div class="pair">
                  <div class="a-field">
                    <label class="a-label" for="re-pw">当前密码</label>
                    <input id="re-pw" ref="reauthInput" v-model="reauthPassword" class="a-input" type="password" autocomplete="current-password">
                  </div>
                  <div class="a-field">
                    <label class="a-label" for="re-code">验证码或恢复码</label>
                    <input id="re-code" v-model="reauthCode" class="a-input otp-sm" type="text" autocomplete="one-time-code" maxlength="11" placeholder="000000">
                  </div>
                </div>
                <div class="row">
                  <button type="submit" class="a-btn" :class="reauth === 'disable' ? 'a-btn-danger' : 'a-btn-primary'" :disabled="!reauthPassword || !reauthCode || mfaBusy">
                    <span v-if="mfaBusy" class="a-spin" />{{ reauth === 'disable' ? '停用' : '生成' }}
                  </button>
                  <button type="button" class="a-btn a-btn-quiet" @click="reauth = null">取消</button>
                </div>
              </form>
              <div v-else class="row">
                <button type="button" class="a-btn" @click="openReauth('regen')"><RefreshCw :size="14" :stroke-width="1.75" /> 重新生成恢复码</button>
                <button type="button" class="a-btn a-btn-quiet is-danger-text" @click="openReauth('disable')">停用</button>
              </div>
            </template>
          </div>
        </div>

        <!-- 修改密码 -->
        <form class="a-card a-rise" style="--i: 3" @submit.prevent="changePassword">
          <header class="a-card-head">
            <div>
              <p class="a-card-title" data-no="B">修改密码</p>
              <p class="a-card-sub">改密后，除这台浏览器外的所有设备都会退出</p>
            </div>
            <KeyRound :size="18" :stroke-width="1.5" class="head-icon" />
          </header>
          <div class="a-card-body pw">
            <input class="sr-only" type="text" name="username" autocomplete="username" :value="adminUser?.username || ''" tabindex="-1" aria-hidden="true" readonly>
            <div class="a-field">
              <label class="a-label" for="pw-cur">当前密码</label>
              <input id="pw-cur" v-model="pw.current" class="a-input" type="password" autocomplete="current-password">
            </div>
            <div class="pair">
              <div class="a-field">
                <label class="a-label" for="pw-new">新密码</label>
                <input id="pw-new" v-model="pw.next" class="a-input" :type="pwShow ? 'text' : 'password'" autocomplete="new-password" maxlength="256">
              </div>
              <div class="a-field">
                <label class="a-label" for="pw-confirm">再输入一次</label>
                <input id="pw-confirm" v-model="pw.confirm" class="a-input" :class="{ 'is-invalid': pwMismatch }" :type="pwShow ? 'text' : 'password'" autocomplete="new-password" maxlength="256">
              </div>
            </div>

            <!-- 强度：四段墨条 -->
            <div class="meter" :data-score="pwScore" aria-live="polite">
              <span v-for="i in 4" :key="i" class="meter-seg" :class="{ 'is-on': pwScore >= i }" />
              <span class="meter-label">{{ pw.next ? PW_LABELS[pwScore] : '' }}</span>
            </div>
            <ul class="rules">
              <li v-for="r in pwRules" :key="r.label" :class="{ 'is-ok': r.ok && pw.next }">
                <Check v-if="r.ok && pw.next" :size="12" :stroke-width="2.25" /><X v-else :size="12" :stroke-width="2" />{{ r.label }}
              </li>
              <li v-if="pwMismatch" class="is-bad"><X :size="12" :stroke-width="2" />两次输入不一致</li>
            </ul>

            <div v-if="overview?.mfa_enabled" class="a-field">
              <label class="a-label" for="pw-code">两步验证码</label>
              <input id="pw-code" v-model="pw.code" class="a-input otp-sm" type="text" autocomplete="one-time-code" maxlength="11" placeholder="000000">
            </div>

            <div class="row">
              <button type="submit" class="a-btn a-btn-primary" :disabled="!pwReady || pwBusy"><span v-if="pwBusy" class="a-spin" />更新密码</button>
              <label class="show"><input v-model="pwShow" type="checkbox"> 显示密码</label>
            </div>
          </div>
        </form>
      </div>

      <div class="stack span-5">
        <!-- 登录会话 -->
        <div class="a-card a-rise" style="--i: 4">
          <header class="a-card-head">
            <div>
              <p class="a-card-title" data-no="C">登录会话</p>
              <p class="a-card-sub">{{ sessions.length }} 台设备 · 7 天不用自动失效</p>
            </div>
            <MonitorSmartphone :size="18" :stroke-width="1.5" class="head-icon" />
          </header>
          <ul class="sessions">
            <li v-for="s in sessions" :key="s.id" class="session" :class="{ 'is-current': s.current }">
              <div class="session-main">
                <p class="session-device">
                  {{ s.device }}
                  <span v-if="s.current" class="a-chip is-here"><i />本机</span>
                  <span v-if="s.mfa" class="a-chip" title="经过两步验证">2FA</span>
                </p>
                <p class="session-meta a-faint">
                  <span class="a-mono">{{ s.ip_masked || '未知网络' }}</span>
                  <span :title="fullTime(s.last_used_at)">活动于 {{ timeAgo(s.last_used_at) }}</span>
                  <span :title="fullTime(s.created_at)">登录于 {{ timeAgo(s.created_at) }}</span>
                </p>
              </div>
              <button v-if="!s.current" type="button" class="a-icon-btn is-danger" :aria-label="`退出 ${s.device}`" title="退出该设备" @click="revokeSession(s)"><LogOut :size="15" :stroke-width="1.5" /></button>
            </li>
            <li v-if="!loading && !sessions.length" class="session a-faint">没有活跃会话</li>
          </ul>
        </div>

        <!-- 安全策略 -->
        <div class="a-card a-rise" style="--i: 5">
          <header class="a-card-head">
            <div>
              <p class="a-card-title" data-no="D">守则</p>
              <p class="a-card-sub">这些规则写在服务端，前端改不了</p>
            </div>
          </header>
          <dl v-if="overview" class="policy">
            <div><dt>访问令牌</dt><dd>{{ overview.policy.access_token_minutes }} 分钟，只存内存</dd></div>
            <div><dt>刷新令牌</dt><dd>HttpOnly Cookie，每次使用即轮换</dd></div>
            <div><dt>会话有效期</dt><dd>{{ overview.policy.session_idle_days }} 天不用失效，最长 {{ overview.policy.session_absolute_days }} 天</dd></div>
            <div><dt>空闲退出</dt><dd>30 分钟无操作自动退出</dd></div>
            <div><dt>登录限流</dt><dd>{{ overview.policy.lockout.window_minutes }} 分钟内同一网络失败 {{ overview.policy.lockout.per_ip }} 次暂停，账号累计 {{ overview.policy.lockout.per_account }} 次锁定</dd></div>
            <div><dt>上传</dt><dd>只收位图，按内容识别格式，单张 15 MB</dd></div>
          </dl>
        </div>
      </div>
    </section>

    <!-- 操作留痕 -->
    <section class="a-card audit a-rise" style="--i: 6">
      <header class="a-card-head">
        <div>
          <p class="a-card-title" data-no="E">操作留痕</p>
          <p class="a-card-sub">共 {{ auditTotal }} 条 · 保留 180 天 · IP 只记前半段</p>
        </div>
        <div class="a-tabs levels" role="tablist" aria-label="按级别筛选">
          <button v-for="l in LEVELS" :key="l.key" type="button" role="tab" class="a-tab" :aria-selected="auditLevel === l.key" @click="setLevel(l.key)">{{ l.label }}</button>
        </div>
        <ScrollText :size="18" :stroke-width="1.5" class="head-icon audit-icon" />
      </header>
      <div class="a-table-wrap is-flush">
        <table class="a-table">
          <thead>
            <tr><th>时间</th><th>动作</th><th>对象</th><th>来源</th><th>操作人</th></tr>
          </thead>
          <tbody>
            <tr v-for="a in audit" :key="a.id" :class="`lv-${a.level}`">
              <td class="when" :title="fullTime(a.at)">{{ timeAgo(a.at) }}</td>
              <td>
                <span class="act"><i class="act-dot" :class="`is-${a.level}`" aria-hidden="true" />{{ actionLabel(a) }}</span>
                <span v-if="actionNote(a)" class="act-note a-faint">{{ actionNote(a) }}</span>
              </td>
              <td class="a-mono a-muted">{{ a.target || '—' }}</td>
              <td class="src a-faint"><span class="a-mono">{{ a.ip_masked || '—' }}</span><template v-if="a.device"> · {{ a.device }}</template></td>
              <td>{{ a.actor || '—' }}</td>
            </tr>
            <tr v-if="!auditLoading && !audit.length"><td colspan="5" class="empty a-faint">这里还没有记录</td></tr>
          </tbody>
        </table>
      </div>
      <div v-if="audit.length < auditTotal" class="more">
        <button type="button" class="a-btn a-btn-quiet" :disabled="auditLoading" @click="loadAudit(false)"><span v-if="auditLoading" class="a-spin" />再看 {{ Math.min(30, auditTotal - audit.length) }} 条</button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.sec { display: flex; flex-direction: column; gap: 16px; }

/* ---------------- 概览 ---------------- */
.figs { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); }
.fig { display: flex; flex-direction: column; gap: 10px; min-height: 128px; padding: 16px 20px 18px; }
.fig + .fig { border-left: 1px solid var(--color-line); }
.fig-label { font-family: var(--font-serif); font-size: 13px; font-weight: 700; letter-spacing: 0.12em; color: var(--color-ink-muted); }
.fig-value { display: flex; align-items: center; min-height: 40px; }
.fig-value.num, .fig-text {
  font-family: var(--font-display);
  font-size: clamp(30px, 2.8vw, 40px);
  font-weight: 500;
  line-height: 1;
  letter-spacing: -0.03em;
  font-variant-numeric: tabular-nums lining-nums;
  font-variation-settings: "opsz" 96, "SOFT" 50;
}
.fig-text { font-size: clamp(20px, 1.8vw, 26px); letter-spacing: -0.01em; }
.fig-value .a-status { height: auto; font-size: 15px; }
.fig-value.is-alert { color: var(--a-danger); }
.fig-sub { margin-top: auto; font-size: 12px; }
.fig-sub.is-warn { color: var(--a-warn); }

/* ---------------- 栅格 ---------------- */
.grid { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 16px; align-items: start; }
.span-7 { grid-column: span 7; }
.span-5 { grid-column: span 5; }
.stack { display: flex; flex-direction: column; gap: 16px; }
.head-icon { color: var(--color-ink-faint); flex-shrink: 0; }
.head-icon.is-ok { color: var(--a-ok); }
.row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.pair { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.step-title { font-family: var(--font-serif); font-size: 15px; font-weight: 700; }
.step-desc { font-size: 13px; line-height: 1.7; }
.inline-form { display: flex; flex-direction: column; gap: 14px; max-width: 440px; }
.is-danger-text { color: var(--a-danger); }
.a-input.is-invalid { border-color: var(--a-danger); }
.otp { font-family: var(--font-mono); font-size: 20px; letter-spacing: 0.42em; height: 44px; font-variant-numeric: tabular-nums; }
.otp-sm { font-family: var(--font-mono); letter-spacing: 0.16em; }
.otp::placeholder, .otp-sm::placeholder { color: var(--color-ink-faint); opacity: 0.5; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }

/* ---------------- 两步验证 ---------------- */
.intro { display: flex; flex-direction: column; align-items: flex-start; gap: 18px; }
.howto { display: flex; flex-direction: column; gap: 10px; font-size: 13.5px; line-height: 1.6; color: var(--color-ink-muted); }
.howto li { display: flex; gap: 12px; }
.howto b { flex-shrink: 0; font-family: var(--font-mono); font-size: 11px; font-weight: 500; letter-spacing: 0.08em; padding-top: 3px; color: var(--color-accent-text); }

.scan { display: grid; grid-template-columns: 184px minmax(0, 1fr); gap: 24px; align-items: start; }
/* 二维码永远是白纸黑墨：深色模式下照样好扫；四角套准线是印刷的语汇 */
.qr { position: relative; margin: 0; padding: 10px; animation: qr-in var(--a-dur-lg) var(--ease-out-expo) both; }
.qr::before, .qr::after {
  content: "";
  position: absolute;
  width: 14px;
  height: 14px;
  border-color: var(--color-ink-faint);
  border-style: solid;
}
.qr::before { left: 0; top: 0; border-width: 1px 0 0 1px; }
.qr::after { right: 0; bottom: 22px; border-width: 0 1px 1px 0; }
.qr svg { display: block; width: 100%; height: auto; border-radius: 2px; }
.qr figcaption { margin-top: 8px; font-family: var(--font-mono); font-size: 10.5px; letter-spacing: 0.12em; text-align: center; color: var(--color-ink-faint); }
@keyframes qr-in { from { opacity: 0; transform: scale(0.96); filter: blur(3px); } }
.secret {
  padding: 10px 12px;
  font-family: var(--font-mono);
  font-size: 13px;
  letter-spacing: 0.08em;
  word-break: break-all;
  user-select: all;
  background: color-mix(in oklab, var(--color-ink) 4%, transparent);
  border: 1px dashed var(--color-line-strong);
  border-radius: var(--a-radius-sm);
}

.codes { display: flex; flex-direction: column; align-items: flex-start; gap: 14px; }
.code-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  width: 100%;
  max-width: 440px;
  border-top: 1px solid var(--color-ink);
}
.code-grid li {
  display: flex;
  align-items: baseline;
  gap: 12px;
  padding: 9px 4px;
  font-family: var(--font-mono);
  font-size: 15px;
  letter-spacing: 0.08em;
  border-bottom: 1px solid var(--color-line);
  user-select: all;
  animation: code-in var(--a-dur-md) var(--ease-out-expo) both;
  animation-delay: calc(var(--n, 0) * 30ms);
}
.code-grid li:nth-child(odd) { border-right: 1px solid var(--color-line); }
.code-grid li:nth-child(even) { padding-left: 14px; }
.code-no { font-size: 10px; letter-spacing: 0.1em; color: var(--color-ink-faint); user-select: none; }
@keyframes code-in { from { opacity: 0; transform: translateY(4px); } }
.ack, .show { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--color-ink-muted); cursor: pointer; }
.show { margin-left: auto; font-size: 12.5px; }

.facts, .policy { display: grid; }
.facts { grid-template-columns: repeat(4, minmax(0, 1fr)); margin-bottom: 18px; border-top: 1px solid var(--color-line); border-bottom: 1px solid var(--color-line); }
.facts > div { padding: 10px 0; }
.facts > div + div { padding-left: 14px; border-left: 1px solid var(--color-line); }
.facts dt, .policy dt { font-size: 11.5px; color: var(--color-ink-faint); }
.facts dd { margin-top: 4px; font-size: 13.5px; }
.reauth { padding-top: 4px; max-width: none; }

/* ---------------- 修改密码 ---------------- */
.pw { display: flex; flex-direction: column; gap: 14px; }
.meter { display: grid; grid-template-columns: repeat(4, 1fr) 48px; align-items: center; gap: 4px; margin-top: -2px; }
.meter-seg {
  height: 3px;
  background: var(--color-line);
  transform-origin: 0 50%;
  transition: background-color var(--a-dur-md) ease;
}
.meter-seg.is-on { animation: seg-in var(--a-dur-md) var(--ease-out-expo); }
.meter[data-score="1"] .meter-seg.is-on { background: var(--a-danger); }
.meter[data-score="2"] .meter-seg.is-on { background: var(--a-warn); }
.meter[data-score="3"] .meter-seg.is-on { background: var(--color-ink-muted); }
.meter[data-score="4"] .meter-seg.is-on { background: var(--a-ok); }
@keyframes seg-in { from { transform: scaleX(0); } }
.meter-label { padding-left: 8px; font-size: 12px; color: var(--color-ink-muted); }
.rules { display: flex; flex-direction: column; gap: 4px; margin-top: -6px; font-size: 12px; color: var(--color-ink-faint); }
.rules li { display: flex; align-items: center; gap: 6px; transition: color var(--a-dur) ease; }
.rules li.is-ok { color: var(--a-ok); }
.rules li.is-bad { color: var(--a-danger); }

/* ---------------- 会话 ---------------- */
.sessions { display: flex; flex-direction: column; }
.session {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 18px;
  font-size: 13px;
  transition: background-color var(--a-dur) ease;
}
.session + .session { border-top: 1px solid var(--color-line); }
.session:hover { background: var(--a-hover); }
.session.is-current::before { content: ""; position: absolute; left: 0; top: 10px; bottom: 10px; width: 2px; background: var(--color-ink); }
.session-main { flex: 1; min-width: 0; }
.session-device { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; font-weight: 600; }
.session-device .a-chip { height: 18px; font-size: 10.5px; font-weight: 500; }
.a-chip.is-here { color: var(--a-ok); border-color: color-mix(in oklab, var(--a-ok) 35%, transparent); }
.session-meta { display: flex; flex-wrap: wrap; gap: 4px 12px; margin-top: 3px; font-size: 12px; }

.policy { padding: 4px 18px 10px; }
.policy > div { display: grid; grid-template-columns: 76px minmax(0, 1fr); gap: 12px; padding: 9px 0; }
.policy > div + div { border-top: 1px solid var(--color-line); }
.policy dt { padding-top: 1px; }
.policy dd { font-size: 12.5px; line-height: 1.6; color: var(--color-ink-muted); }

/* ---------------- 操作留痕 ---------------- */
.audit .a-card-head { flex-wrap: wrap; }
.levels { margin-left: auto; border-bottom: 0; }
.levels .a-tab { height: 30px; }
.audit-icon { margin-left: 8px; }
.a-table-wrap.is-flush { border: 0; border-radius: 0; }
.audit .a-table td { height: 46px; }
.when { white-space: nowrap; font-size: 12.5px; color: var(--color-ink-muted); font-variant-numeric: tabular-nums; }
.act { display: inline-flex; align-items: center; gap: 8px; font-weight: 500; }
.act-dot { width: 7px; height: 7px; border-radius: 1px; background: var(--color-ink-faint); }
.act-dot.is-warn { background: transparent; box-shadow: inset 0 0 0 1.5px var(--a-warn); }
.act-dot.is-danger { background: var(--a-danger); }
.act-note { margin-left: 8px; font-size: 12px; }
.lv-danger .act { color: var(--a-danger); }
.src { font-size: 12px; white-space: nowrap; }
.empty { padding: 28px 14px; text-align: center; }
.more { display: flex; justify-content: center; padding: 10px; border-top: 1px solid var(--color-line); }

@media (max-width: 1180px) {
  .figs { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .fig:nth-child(4) { border-left: 0; }
  .fig:nth-child(n + 4) { border-top: 1px solid var(--color-line); }
  .span-7, .span-5 { grid-column: 1 / -1; }
}
@media (max-width: 640px) {
  .figs { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .fig { min-height: 110px; padding: 14px 16px; }
  .fig:nth-child(n) { border-left: 0; border-top: 0; }
  .fig:nth-child(even) { border-left: 1px solid var(--color-line); }
  .fig:nth-child(n + 3) { border-top: 1px solid var(--color-line); }
  .pair, .scan { grid-template-columns: 1fr; }
  .qr { max-width: 220px; }
  .facts { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .facts > div:nth-child(3) { padding-left: 0; border-left: 0; }
  .facts > div:nth-child(n + 3) { border-top: 1px solid var(--color-line); }
  .code-grid { grid-template-columns: 1fr; }
  .code-grid li:nth-child(odd) { border-right: 0; }
  .code-grid li:nth-child(even) { padding-left: 4px; }
}
:global(html.reduce-motion) .qr,
:global(html.reduce-motion) .code-grid li,
:global(html.reduce-motion) .meter-seg.is-on { animation: none; }
</style>

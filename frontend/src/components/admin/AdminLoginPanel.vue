<template>
  <section class="max-w-md mx-auto mt-16 bg-white rounded-2xl shadow-sm border border-slate-200 p-8">
    <header class="mb-6">
      <p class="text-xs font-semibold tracking-[0.2em] text-red-700 uppercase">Operations Console</p>
      <h1 class="text-2xl font-bold text-slate-900 mt-2">运营数据质量工作台</h1>
      <p class="text-sm text-slate-500 mt-2">
        管理员凭据由服务端环境变量注入；匿名聊天会话令牌不能访问后台。
      </p>
    </header>

    <form class="space-y-4" @submit.prevent="submit" novalidate>
      <div>
        <label for="admin-username" class="block text-sm font-medium text-slate-700 mb-1">用户名</label>
        <input
          id="admin-username"
          v-model="username"
          data-testid="admin-username"
          autocomplete="username"
          class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
          placeholder="operator"
          required
        />
      </div>
      <div>
        <label for="admin-password" class="block text-sm font-medium text-slate-700 mb-1">密码</label>
        <input
          id="admin-password"
          v-model="password"
          data-testid="admin-password"
          type="password"
          autocomplete="current-password"
          class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
          placeholder="至少 8 位"
          required
        />
      </div>

      <p v-if="admin.actionError" role="alert" data-testid="login-error" class="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
        {{ admin.actionError }}
      </p>

      <button
        type="submit"
        data-testid="admin-login-submit"
        :disabled="admin.actionPending || !username || password.length < 8"
        class="w-full rounded-lg bg-red-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-red-800 disabled:opacity-40"
      >
        {{ admin.actionPending ? '登录中…' : '登录后台' }}
      </button>
    </form>

    <div class="mt-6 rounded-lg bg-slate-50 border border-slate-200 p-3 text-xs text-slate-600 leading-relaxed">
      <p class="font-semibold text-slate-700 mb-1">本地演示配置</p>
      <code class="block break-all">ADMIN_USERS_JSON='[{"username":"operator",...}]'</code>
      <code class="block break-all">ADMIN_TOKEN_SECRET=至少 32 字符</code>
      <p class="mt-1">使用 <code>python scripts/hash_admin_password.py --json</code> 生成密码哈希。</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useAdminStore } from '../../stores/admin'

const admin = useAdminStore()
const username = ref('operator')
const password = ref('')

async function submit(): Promise<void> {
  if (!username.value || password.value.length < 8) return
  await admin.login(username.value, password.value)
  if (admin.isAuthenticated) password.value = ''
}
</script>

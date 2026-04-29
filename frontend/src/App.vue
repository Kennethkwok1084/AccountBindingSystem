<template>
  <a-config-provider :locale="zhCN">
    <template v-if="isLogin">
      <router-view />
    </template>
    <a-layout v-else style="min-height: 100vh;">
      <a-layout-sider
        :width="220"
        theme="dark"
        style="position: sticky; top: 0; height: 100vh; overflow-y: auto; overflow-x: hidden;"
      >
        <div class="sidebar-logo">账号池系统</div>
        <a-menu theme="dark" mode="inline" :selected-keys="selectedKeys">
          <a-menu-item-group title="总览">
            <a-menu-item key="/dashboard" @click="router.push('/dashboard')">仪表盘</a-menu-item>
            <a-menu-item key="/alerts" @click="router.push('/alerts')">预警中心</a-menu-item>
            <a-menu-item key="/exports" @click="router.push('/exports')">导出记录</a-menu-item>
          </a-menu-item-group>
          <a-menu-item-group title="导入">
            <a-menu-item key="/imports/account-pool" @click="router.push('/imports/account-pool')">账号导入</a-menu-item>
            <a-menu-item key="/imports/full-list" @click="router.push('/imports/full-list')">完整名单</a-menu-item>
            <a-menu-item key="/operations/charge-preview" @click="router.push('/operations/charge-preview')">收费清单</a-menu-item>
            <a-menu-item key="/imports/charge-archive" @click="router.push('/imports/charge-archive')">收费归档</a-menu-item>
          </a-menu-item-group>
          <a-menu-item-group title="运营">
            <a-menu-item key="/operations/manual-rebind" @click="router.push('/operations/manual-rebind')">手动换绑</a-menu-item>
            <a-menu-item key="/operations/batch-rebind" @click="router.push('/operations/batch-rebind')">批次到期批量换号</a-menu-item>
            <a-menu-item key="/accounts" @click="router.push('/accounts')">账号管理</a-menu-item>
            <a-menu-item key="/batches" @click="router.push('/batches')">批次管理</a-menu-item>
          </a-menu-item-group>
          <a-menu-item-group title="台账">
            <a-menu-item key="/ledger/students" @click="router.push('/ledger/students')">学生台账</a-menu-item>
            <a-menu-item key="/ledger/accounts" @click="router.push('/ledger/accounts')">账号台账</a-menu-item>
          </a-menu-item-group>
          <a-menu-item-group title="系统">
            <a-menu-item key="/settings" @click="router.push('/settings')">系统设置</a-menu-item>
            <a-menu-item key="/audit-logs" @click="router.push('/audit-logs')">审计日志</a-menu-item>
          </a-menu-item-group>
        </a-menu>
      </a-layout-sider>

      <a-layout>
        <a-layout-header
          style="background: #fff; padding: 0 24px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #f0f0f0; position: sticky; top: 0; z-index: 10;"
        >
          <div style="flex: 1; margin-right: 16px;">
            <a-alert
              v-if="globalError"
              type="error"
              :message="globalError.message"
              :description="globalError.code ? `错误码：${globalError.code}` : undefined"
              show-icon
              closable
              @close="clearGlobalError"
              banner
            />
          </div>
          <a-button @click="handleLogout">退出登录</a-button>
        </a-layout-header>
        <a-layout-content style="padding: 24px; min-width: 0;">
          <router-view />
        </a-layout-content>
      </a-layout>
    </a-layout>
  </a-config-provider>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { fetchAuthMode, logout } from "./services/auth";
import zhCN from "ant-design-vue/es/locale/zh_CN";

const route = useRoute();
const router = useRouter();
const isLogin = computed(() => route.path === "/login");
const globalError = ref(null);
const selectedKeys = computed(() => [route.path]);

function setGlobalError(payload) {
  if (!payload) return;
  globalError.value = {
    message: payload.message || "发生未知错误",
    code: payload.code || "",
    requestId: payload.requestId || "",
    path: payload.path || "",
    method: payload.method || "",
  };
}

function clearGlobalError() {
  globalError.value = null;
}

function handleApiError(event) {
  setGlobalError(event.detail || {});
}

function handleRuntimeError(event) {
  const detail = event?.detail || {};
  setGlobalError({
    message: detail.message || "前端运行异常",
    code: detail.code || "RUNTIME_ERROR",
  });
}

function handleUnhandledRejection(event) {
  const reason = event?.reason;
  if (!reason) return;
  if (typeof reason === "string") {
    setGlobalError({ message: reason, code: "UNHANDLED_REJECTION" });
    return;
  }
  setGlobalError({
    message: reason.message || "未捕获的 Promise 异常",
    code: reason.code || "UNHANDLED_REJECTION",
    requestId: reason.requestId || "",
    path: reason.path || "",
    method: reason.method || "",
  });
}

async function handleLogout() {
  const mode = await fetchAuthMode();
  await logout();
  if (mode.local_login_enabled) {
    router.push("/login");
    return;
  }
  window.location.href = "/login";
}

onMounted(() => {
  window.addEventListener("abs-api-error", handleApiError);
  window.addEventListener("abs-runtime-error", handleRuntimeError);
  window.addEventListener("unhandledrejection", handleUnhandledRejection);
});

onBeforeUnmount(() => {
  window.removeEventListener("abs-api-error", handleApiError);
  window.removeEventListener("abs-runtime-error", handleRuntimeError);
  window.removeEventListener("unhandledrejection", handleUnhandledRejection);
});
</script>

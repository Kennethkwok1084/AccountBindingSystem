<template>
  <div class="app-shell">
    <aside class="sidebar" v-if="!isLogin">
      <h1>账号池系统</h1>
      <nav class="sidebar-nav">
        <section class="nav-group">
          <p class="nav-title">总览</p>
          <RouterLink to="/dashboard">仪表盘</RouterLink>
          <RouterLink to="/alerts">预警中心</RouterLink>
          <RouterLink to="/exports">导出记录</RouterLink>
        </section>

        <section class="nav-group">
          <p class="nav-title">导入</p>
          <RouterLink to="/imports/account-pool">账号导入</RouterLink>
          <RouterLink to="/imports/full-list">完整名单</RouterLink>
          <RouterLink to="/operations/charge-preview">收费清单</RouterLink>
        </section>

        <section class="nav-group">
          <p class="nav-title">运营</p>
          <RouterLink to="/operations/manual-rebind">手动换绑</RouterLink>
          <RouterLink to="/operations/batch-rebind">批次换绑</RouterLink>
          <RouterLink to="/accounts">账号管理</RouterLink>
          <RouterLink to="/batches">批次管理</RouterLink>
        </section>

        <section class="nav-group">
          <p class="nav-title">台账</p>
          <RouterLink to="/ledger/students">学生台账</RouterLink>
          <RouterLink to="/ledger/accounts">账号台账</RouterLink>
        </section>

        <section class="nav-group">
          <p class="nav-title">系统</p>
          <RouterLink to="/settings">系统设置</RouterLink>
        </section>
      </nav>
    </aside>
    <main class="content">
      <header class="topbar" v-if="!isLogin">
        <button class="link-button" @click="handleLogout">退出登录</button>
      </header>
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router";
import { logout } from "./services/auth";

const route = useRoute();
const router = useRouter();
const isLogin = computed(() => route.path === "/login");

async function handleLogout() {
  await logout();
  router.push("/login");
}
</script>

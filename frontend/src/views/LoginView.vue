<template>
  <section class="panel narrow">
    <h2>管理员登录</h2>
    <form @submit.prevent="submit">
      <label>用户名</label>
      <input v-model="username" placeholder="admin" />
      <label>密码</label>
      <input v-model="password" type="password" placeholder="请输入密码" />
      <button type="submit">登录</button>
      <p class="error" v-if="errorMessage">{{ errorMessage }}</p>
    </form>
  </section>
</template>

<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { login } from "../services/auth";

const router = useRouter();
const username = ref("admin");
const password = ref("");
const errorMessage = ref("");

async function submit() {
  errorMessage.value = "";
  try {
    await login(username.value, password.value);
    router.push("/dashboard");
  } catch (error) {
    errorMessage.value = error.message;
  }
}
</script>

<template>
  <div style="min-height: 100vh; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);">
    <a-card
      title="账号池系统"
      :bordered="false"
      style="width: 400px; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.3);"
    >
      <a-form layout="vertical" @submit.prevent="submit">
        <a-form-item label="用户名">
          <a-input v-model:value="username" placeholder="请输入用户名" size="large" allow-clear @pressEnter="submit" />
        </a-form-item>
        <a-form-item label="密码">
          <a-input-password v-model:value="password" placeholder="请输入密码" size="large" @pressEnter="submit" />
        </a-form-item>
        <a-alert
          v-if="errorMessage"
          type="error"
          :message="errorMessage"
          show-icon
          style="margin-bottom: 16px;"
        />
        <a-button type="primary" html-type="submit" size="large" block :loading="submitting" @click="submit">登录</a-button>
      </a-form>
    </a-card>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { login } from "../services/auth";

const router = useRouter();
const username = ref("admin");
const password = ref("");
const errorMessage = ref("");
const submitting = ref(false);

async function submit() {
  if (submitting.value) {
    return;
  }
  errorMessage.value = "";
  submitting.value = true;
  try {
    await login(username.value, password.value);
    router.push("/dashboard");
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    submitting.value = false;
  }
}
</script>

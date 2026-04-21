<template>
  <section class="panel">
    <h2>手动换绑</h2>
    <form @submit.prevent="submit">
      <label>学号</label>
      <input v-model="studentNo" />
      <label>新账号 ID</label>
      <input v-model="newAccountId" type="number" />
      <label>旧号处理方式</label>
      <select v-model="oldAccountAction">
        <option value="release">释放</option>
        <option value="disable">禁用</option>
      </select>
      <label>备注</label>
      <textarea v-model="remark"></textarea>
      <button type="submit" :disabled="submitting">{{ submitting ? "执行中..." : "执行换绑" }}</button>
    </form>
    <p v-if="message" class="message">{{ message }}</p>
  </section>
</template>

<script setup>
import { computed, ref } from "vue";
import { apiFetch, createIdempotencyKey } from "../services/api";
import { useLeaveGuard } from "../composables/useLeaveGuard";

const studentNo = ref("");
const newAccountId = ref("");
const oldAccountAction = ref("release");
const remark = ref("");
const message = ref("");
const submitting = ref(false);

const isDirty = computed(() => Boolean(studentNo.value || newAccountId.value || remark.value));
useLeaveGuard(isDirty, "手动换绑表单尚未提交，离开后输入会丢失，确定离开吗？");

async function submit() {
  if (!window.confirm("确认执行当前手动换绑吗？")) {
    return;
  }
  submitting.value = true;
  try {
    const payload = await apiFetch("/api/v1/bindings/manual-rebind", {
      method: "POST",
      headers: {
        "X-Idempotency-Key": createIdempotencyKey("manual-rebind"),
      },
      body: JSON.stringify({
        student_no: studentNo.value,
        new_account_id: Number(newAccountId.value),
        old_account_action: oldAccountAction.value,
        remark: remark.value,
      }),
    });
    message.value = `换绑完成：${payload.data.old_account} -> ${payload.data.new_account}`;
    studentNo.value = "";
    newAccountId.value = "";
    remark.value = "";
  } finally {
    submitting.value = false;
  }
}
</script>

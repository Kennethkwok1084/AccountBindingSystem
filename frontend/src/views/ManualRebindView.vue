<template>
  <a-card :bordered="false">
    <template #title>手动换绑</template>

    <a-alert
      type="info"
      message="对单个学生执行手动换绑操作，填写后确认提交。离开页面时若有未保存内容会提示。"
      style="margin-bottom: 20px;"
    />

    <a-form layout="vertical" :model="formModel" style="max-width: 520px;" @finish="handleSubmit">
      <a-form-item label="学号" required>
        <a-input v-model:value="studentNo" placeholder="输入学号" allow-clear />
      </a-form-item>
      <a-form-item label="新账号 ID" required>
        <a-input-number v-model:value="newAccountId" placeholder="输入新账号 ID" style="width: 100%;" :min="1" />
      </a-form-item>
      <a-form-item label="旧号处理方式" required>
        <a-select v-model:value="oldAccountAction" style="width: 100%;">
          <a-select-option value="release">释放</a-select-option>
          <a-select-option value="disable">禁用</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item label="备注">
        <a-textarea v-model:value="remark" placeholder="可选备注" :rows="3" />
      </a-form-item>
      <a-form-item>
        <a-button type="primary" html-type="submit" :loading="submitting" :disabled="!studentNo || !newAccountId">
          执行换绑
        </a-button>
      </a-form-item>
    </a-form>
  </a-card>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { Modal, message } from "ant-design-vue";
import { apiFetch, createIdempotencyKey } from "../services/api";
import { useLeaveGuard } from "../composables/useLeaveGuard";

const route = useRoute();
const studentNo = ref("");
const newAccountId = ref(null);
const oldAccountAction = ref("release");
const remark = ref("");
const submitting = ref(false);

const formModel = computed(() => ({ studentNo: studentNo.value, newAccountId: newAccountId.value }));
const isDirty = computed(() => Boolean(studentNo.value || newAccountId.value || remark.value));
useLeaveGuard(isDirty, "手动换绑表单尚未提交，离开后输入会丢失，确定离开吗？");

function handleSubmit() {
  Modal.confirm({
    title: "确认执行换绑",
    content: `确认对学号 ${studentNo.value} 执行手动换绑吗？`,
    okText: "确认执行",
    cancelText: "取消",
    onOk: doSubmit,
  });
}

async function doSubmit() {
  submitting.value = true;
  try {
    const payload = await apiFetch("/api/v1/bindings/manual-rebind", {
      method: "POST",
      headers: { "X-Idempotency-Key": createIdempotencyKey("manual-rebind") },
      body: JSON.stringify({
        student_no: studentNo.value,
        new_account_id: Number(newAccountId.value),
        old_account_action: oldAccountAction.value,
        remark: remark.value,
      }),
    });
    message.success(`换绑完成：${payload.data.old_account} → ${payload.data.new_account}`);
    studentNo.value = "";
    newAccountId.value = null;
    remark.value = "";
  } finally {
    submitting.value = false;
  }
}

onMounted(() => {
  if (route.query.student_no) {
    studentNo.value = String(route.query.student_no);
  }
});
</script>

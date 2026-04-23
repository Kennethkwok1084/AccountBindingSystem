<template>
  <a-card :bordered="false">
    <template #title>手动换绑</template>

    <a-alert
      type="info"
      message="对单个学生执行手动换绑操作。提交后系统会自动从未绑定的可用账号中抽取一个新号。"
      style="margin-bottom: 20px;"
    />

    <a-alert
      v-if="successState"
      type="success"
      message="换绑已完成"
      show-icon
      style="margin-bottom: 20px;"
    >
      <template #description>
        <div style="margin-bottom: 12px;">
          学号 {{ successState.studentNo }} 已从 {{ successState.oldAccount }} 换绑到 {{ successState.newAccount }}。
          导出文件已生成：{{ successState.exportFilename }}。请前往导出记录页面下载。
        </div>
        <a-space wrap>
          <a-button type="primary" @click="goToExports">前往导出记录</a-button>
          <a-button @click="clearSuccess">关闭提示</a-button>
        </a-space>
      </template>
    </a-alert>

    <a-form layout="vertical" :model="formModel" style="max-width: 520px;" @finish="handleSubmit">
      <a-form-item label="学号" required>
        <a-input v-model:value="studentNo" placeholder="输入学号" allow-clear />
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
        <a-button type="primary" html-type="submit" :loading="submitting" :disabled="!studentNo">
          执行换绑
        </a-button>
      </a-form-item>
    </a-form>
  </a-card>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Modal } from "ant-design-vue";
import { apiFetch, createIdempotencyKey } from "../services/api";
import { useLeaveGuard } from "../composables/useLeaveGuard";

const route = useRoute();
const router = useRouter();
const studentNo = ref("");
const oldAccountAction = ref("release");
const remark = ref("");
const submitting = ref(false);
const successState = ref(null);

const formModel = computed(() => ({ studentNo: studentNo.value }));
const isDirty = computed(() => Boolean(studentNo.value || remark.value));
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
    successState.value = null;
    const payload = await apiFetch("/api/v1/bindings/manual-rebind", {
      method: "POST",
      headers: { "X-Idempotency-Key": createIdempotencyKey("manual-rebind") },
      body: JSON.stringify({
        student_no: studentNo.value,
        old_account_action: oldAccountAction.value,
        remark: remark.value,
      }),
    });
    successState.value = {
      studentNo: payload.data.student_no,
      oldAccount: payload.data.old_account,
      newAccount: payload.data.new_account,
      exportFilename: payload.data.export_job?.filename || "导出文件",
    };
    studentNo.value = "";
    remark.value = "";
  } finally {
    submitting.value = false;
  }
}

function goToExports() {
  if (!successState.value?.exportFilename) {
    router.push("/exports");
    return;
  }
  router.push({
    path: "/exports",
    query: { keyword: successState.value.exportFilename },
  });
}

function clearSuccess() {
  successState.value = null;
}

onMounted(() => {
  if (route.query.student_no) {
    studentNo.value = String(route.query.student_no);
  }
});
</script>

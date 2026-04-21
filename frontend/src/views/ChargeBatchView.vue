<template>
  <section class="panel">
    <div class="section-heading">
      <div>
        <h2>收费清单执行</h2>
        <p class="muted">点击执行后会弹窗展示预览，确认后才会真正写入。</p>
      </div>
    </div>

    <form class="inline-form" @submit.prevent="submitAndConfirm">
      <input ref="fileInput" type="file" accept=".xlsx,.xls" @change="onFileChange" />
      <button type="submit" :disabled="executing || previewing">{{ previewing ? "预览中..." : executing ? "执行中..." : "执行" }}</button>
    </form>

    <p v-if="message" class="message">{{ message }}</p>

    <div v-if="confirmVisible && previewData" class="confirm-overlay" @click.self="closeConfirm">
      <div class="confirm-modal">
        <h3>执行前预览</h3>
        <p>批次 ID：{{ previewData.operation_batch_id }}</p>
        <p>新分配 {{ previewData.to_allocate_count }} / 续费 {{ previewData.to_renew_count }} / 换绑 {{ previewData.to_rebind_count }} / 失败 {{ previewData.fail_count }}</p>
        <div class="scroll-box">
          <table>
            <thead>
              <tr>
                <th>行号</th>
                <th>学号</th>
                <th>姓名</th>
                <th>动作</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in previewRows" :key="row.row_no">
                <td>{{ row.row_no }}</td>
                <td>{{ row.student_no }}</td>
                <td>{{ row.name }}</td>
                <td>{{ row.action_plan }}</td>
                <td>{{ row.result_message }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="previewData.details.length > 20" class="muted">仅展示前 20 条，确认后将执行全部预览数据。</p>
        <div class="actions">
          <button type="button" class="link-button" @click="closeConfirm">取消</button>
          <button type="button" :disabled="executing" @click="executeConfirmed">{{ executing ? "执行中..." : "确认执行" }}</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from "vue";
import { apiFetch, createIdempotencyKey } from "../services/api";
import { useLeaveGuard } from "../composables/useLeaveGuard";

const file = ref(null);
const fileInput = ref(null);
const previewData = ref(null);
const confirmVisible = ref(false);
const message = ref("");
const executing = ref(false);
const previewing = ref(false);
const hasPendingPreview = computed(() => Boolean(file.value || previewData.value));
const previewRows = computed(() => previewData.value?.details?.slice(0, 20) || []);

useLeaveGuard(hasPendingPreview, "收费清单已经选择或生成预览，离开后需要重新上传，确定离开吗？");

function onFileChange(event) {
  file.value = event.target.files[0] || null;
}

async function submitAndConfirm() {
  if (!file.value) {
    message.value = "请先选择收费清单文件";
    return;
  }
  message.value = "";
  previewing.value = true;
  try {
    const formData = new FormData();
    formData.append("file", file.value);
    const payload = await apiFetch("/api/v1/charge-batches/preview", {
      method: "POST",
      body: formData,
    });
    previewData.value = payload.data;
    confirmVisible.value = true;
  } catch (error) {
    message.value = error.message || "生成预览失败";
    confirmVisible.value = false;
    previewData.value = null;
  } finally {
    previewing.value = false;
  }
}

function closeConfirm() {
  confirmVisible.value = false;
  previewData.value = null;
}

async function executeConfirmed() {
  if (!previewData.value) {
    return;
  }
  executing.value = true;
  try {
    const payload = await apiFetch(`/api/v1/charge-batches/${previewData.value.operation_batch_id}/execute`, {
      method: "POST",
      headers: {
        "X-Idempotency-Key": createIdempotencyKey("charge"),
      },
      body: JSON.stringify({ confirm: true }),
    });
    message.value = `执行完成：成功 ${payload.data.success_count}，失败 ${payload.data.fail_count}`;
    file.value = null;
    if (fileInput.value) {
      fileInput.value.value = "";
    }
    previewData.value = null;
    confirmVisible.value = false;
  } finally {
    executing.value = false;
  }
}
</script>

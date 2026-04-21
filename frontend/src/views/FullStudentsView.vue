<template>
  <section class="panel">
    <h2>完整名单导入</h2>
    <form class="inline-form" @submit.prevent="submitAndConfirm">
      <input ref="fileInput" type="file" accept=".xlsx,.xls" @change="onFileChange" />
      <button type="submit" :disabled="executing || previewing">{{ previewing ? "预览中..." : executing ? "执行中..." : "执行" }}</button>
    </form>
    <p v-if="message" class="message">{{ message }}</p>
    <div v-if="confirmVisible && previewData" class="confirm-overlay" @click.self="closeConfirm">
      <div class="confirm-modal">
        <h3>执行前预览</h3>
        <p>任务 ID：{{ previewData.job_id }}</p>
        <p>释放 {{ previewData.release_count }} / 冲突 {{ previewData.conflict_count }}</p>
        <div class="scroll-box">
          <ul>
            <li v-for="row in previewRows" :key="row.row_no">
              {{ row.student_no }} / {{ row.name }} / {{ row.expire_at }} <span v-if="row.conflict">[冲突]</span>
            </li>
          </ul>
        </div>
        <p v-if="previewData.preview.length > 20" class="muted">仅展示前 20 条，确认后将执行全部预览数据。</p>
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

const file = ref(null);
const fileInput = ref(null);
const previewData = ref(null);
const confirmVisible = ref(false);
const message = ref("");
const executing = ref(false);
const previewing = ref(false);
const previewRows = computed(() => previewData.value?.preview?.slice(0, 20) || []);

function onFileChange(event) {
  file.value = event.target.files[0] || null;
}

async function submitAndConfirm() {
  if (!file.value) {
    message.value = "请先选择完整名单文件";
    return;
  }
  message.value = "";
  previewing.value = true;
  try {
    const formData = new FormData();
    formData.append("file", file.value);
    const payload = await apiFetch("/api/v1/full-students/import/preview", {
      method: "POST",
      body: formData,
    });
    previewData.value = payload.data;
    confirmVisible.value = true;
  } catch (error) {
    message.value = error.message || "生成预览失败";
    previewData.value = null;
    confirmVisible.value = false;
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
    const payload = await apiFetch(`/api/v1/full-students/import/${previewData.value.job_id}/execute`, {
      method: "POST",
      headers: {
        "X-Idempotency-Key": createIdempotencyKey("full-students"),
      },
      body: JSON.stringify({ confirm: true }),
    });
    message.value = `执行完成：成功 ${payload.data.success_rows}，释放 ${payload.data.released_rows}，冲突 ${payload.data.conflicts}`;
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

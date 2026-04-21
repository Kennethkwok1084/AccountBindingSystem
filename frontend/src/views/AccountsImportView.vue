<template>
  <section class="panel">
    <div class="section-heading">
      <div>
        <h2>账号池导入</h2>
        <p class="muted">上传 Excel 导入账号池，支持查看失败明细与模板下载。</p>
      </div>
    </div>
    <form class="import-form" @submit.prevent="submit">
      <input ref="fileInput" type="file" accept=".xlsx,.xls" @change="onFileChange" />
      <button class="import-submit" type="submit" :disabled="submitting">{{ submitting ? "上传中..." : "上传导入" }}</button>
      <a class="template-download" href="/api/v1/mobile-accounts/template" target="_blank" rel="noopener">下载模板 Excel</a>
      <button type="button" class="link-button" @click="loadAccounts">刷新账号列表</button>
    </form>
    <div v-if="submitting" class="upload-progress">
      <div class="progress-track">
        <div class="progress-fill" :style="{ width: `${uploadProgress}%` }"></div>
      </div>
      <p class="muted">上传进度 {{ uploadProgress }}%</p>
    </div>
    <p v-if="message" class="message">{{ message }}</p>
    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
    <div v-if="importErrors.length" class="subpanel">
      <h3>导入错误明细</h3>
      <table>
        <thead>
          <tr>
            <th>行号</th>
            <th>字段</th>
            <th>错误码</th>
            <th>说明</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, index) in importErrors" :key="`${item.row_no}-${item.field_name || 'none'}-${index}`">
            <td>{{ item.row_no === 0 ? "模板" : item.row_no }}</td>
            <td>{{ item.field_name || "-" }}</td>
            <td>{{ item.error_code }}</td>
            <td>{{ item.error_message }}</td>
          </tr>
        </tbody>
      </table>
      <div class="table-footer">
        <span class="muted">共 {{ errorTotal }} 条错误，第 {{ errorPage }} / {{ errorTotalPages }} 页</span>
        <div class="actions">
          <button type="button" class="link-button" :disabled="errorPage <= 1 || !currentImportJobId" @click="loadImportErrors(currentImportJobId, errorPage - 1)">上一页</button>
          <button type="button" class="link-button" :disabled="errorPage >= errorTotalPages || !currentImportJobId" @click="loadImportErrors(currentImportJobId, errorPage + 1)">下一页</button>
        </div>
      </div>
    </div>

    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>账号</th>
          <th>状态</th>
          <th>批次</th>
          <th>类型</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in pagedAccounts" :key="item.id">
          <td>{{ item.id }}</td>
          <td>{{ item.account }}</td>
          <td>{{ item.status }}</td>
          <td>{{ item.batch_code }}</td>
          <td>{{ item.batch_type }}</td>
        </tr>
      </tbody>
    </table>
    <div class="table-footer">
      <span class="muted">共 {{ accounts.length }} 条账号，第 {{ accountsPage }} / {{ accountsTotalPages }} 页</span>
      <div class="actions">
        <button type="button" class="link-button" :disabled="accountsPage <= 1" @click="accountsPage -= 1">上一页</button>
        <button type="button" class="link-button" :disabled="accountsPage >= accountsTotalPages" @click="accountsPage += 1">下一页</button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { apiFetch } from "../services/api";

const file = ref(null);
const fileInput = ref(null);
const message = ref("");
const errorMessage = ref("");
const importErrors = ref([]);
const currentImportJobId = ref(null);
const errorPage = ref(1);
const errorPageSize = 20;
const errorTotal = ref(0);
const accounts = ref([]);
const submitting = ref(false);
const uploadProgress = ref(0);
const accountsPage = ref(1);
const accountsPageSize = 20;

const pagedAccounts = computed(() => {
  const start = (accountsPage.value - 1) * accountsPageSize;
  return accounts.value.slice(start, start + accountsPageSize);
});
const accountsTotalPages = computed(() => Math.max(1, Math.ceil(accounts.value.length / accountsPageSize)));
const errorTotalPages = computed(() => Math.max(1, Math.ceil(errorTotal.value / errorPageSize)));

function onFileChange(event) {
  file.value = event.target.files[0] || null;
}

async function submit() {
  message.value = "";
  errorMessage.value = "";
  importErrors.value = [];
  errorTotal.value = 0;
  errorPage.value = 1;
  currentImportJobId.value = null;
  if (!file.value) {
    errorMessage.value = "请先选择文件";
    return;
  }
  submitting.value = true;
  uploadProgress.value = 0;
  try {
    const payload = await uploadImportFile(file.value, (percent) => {
      uploadProgress.value = percent;
    });
    message.value = `导入完成：成功 ${payload.data.success_rows} 行，失败 ${payload.data.failed_rows} 行`;
    if (payload.data.failed_rows > 0) {
      await loadImportErrors(payload.data.job_id, 1);
    }
    await loadAccounts();
    resetSelectedFile();
  } catch (error) {
    errorMessage.value = error.message || "账号导入失败";
    importErrors.value = Array.isArray(error.details) ? error.details : [];
    errorTotal.value = importErrors.value.length;
  } finally {
    submitting.value = false;
    uploadProgress.value = 0;
  }
}

async function loadAccounts() {
  const payload = await apiFetch("/api/v1/mobile-accounts");
  accounts.value = payload.data.items;
  accountsPage.value = 1;
}

async function loadImportErrors(jobId, page = 1) {
  if (!jobId) {
    return;
  }
  const payload = await apiFetch(`/api/v1/imports/${jobId}?page=${page}&page_size=${errorPageSize}`);
  importErrors.value = payload.data.errors.items;
  errorTotal.value = payload.data.errors.total;
  errorPage.value = payload.data.errors.page;
  currentImportJobId.value = jobId;
}

function resetSelectedFile() {
  file.value = null;
  if (fileInput.value) {
    fileInput.value.value = "";
  }
}

function uploadImportFile(selectedFile, onProgress) {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append("file", selectedFile);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/v1/mobile-accounts/import");
    xhr.withCredentials = true;
    const csrfToken = sessionStorage.getItem("csrf_token") || "";
    if (csrfToken) {
      xhr.setRequestHeader("X-CSRF-Token", csrfToken);
    }
    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable) {
        return;
      }
      const percent = Math.min(100, Math.max(0, Math.round((event.loaded / event.total) * 100)));
      onProgress(percent);
    };
    xhr.onload = () => {
      const contentType = xhr.getResponseHeader("content-type") || "";
      let payload = null;
      if (contentType.includes("application/json")) {
        try {
          payload = JSON.parse(xhr.responseText);
        } catch (_error) {
          payload = null;
        }
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(payload);
        return;
      }
      const fallbackMessage = xhr.status === 413 ? "上传文件过大，请压缩后重试（当前上限 64MB）" : "请求失败";
      const error = new Error(payload?.message || fallbackMessage);
      error.code = payload?.code || "REQUEST_FAILED";
      error.details = payload?.details || [];
      reject(error);
    };
    xhr.onerror = () => {
      reject(new Error("网络异常，请稍后重试"));
    };
    xhr.send(formData);
  });
}

onMounted(loadAccounts);
</script>

<style scoped>
.import-form {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) auto auto auto;
  gap: 10px;
  align-items: center;
}

.import-form input[type="file"] {
  height: 44px;
  padding: 8px 12px;
}

.import-submit {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 44px;
  white-space: nowrap;
  min-width: 98px;
}

.import-form .link-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 44px;
  white-space: nowrap;
}

.template-download {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
  min-width: 140px;
  height: 44px;
  border-radius: 10px;
  padding: 0 16px;
  border: 1px solid rgba(148, 163, 184, 0.3);
  color: #ffffff;
  background: #1e293b;
  font-weight: 600;
  line-height: 1;
  text-decoration: none;
  transition: background-color 0.15s ease, border-color 0.15s ease;
}

.template-download:hover {
  background: #0f172a;
  border-color: rgba(148, 163, 184, 0.45);
}

.template-download:focus-visible {
  outline: 2px solid #60a5fa;
  outline-offset: 2px;
}

.upload-progress {
  margin-top: 12px;
}

.progress-track {
  width: 100%;
  height: 10px;
  border-radius: 999px;
  background: #e2e8f0;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #2563eb 0%, #0ea5e9 100%);
  transition: width 0.2s ease;
}

.table-footer {
  margin-top: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

@media (max-width: 960px) {
  .import-form {
    grid-template-columns: 1fr;
  }
}
</style>

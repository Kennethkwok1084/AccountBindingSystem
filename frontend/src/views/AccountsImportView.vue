<template>
  <a-card :bordered="false">
    <template #title>账号池导入</template>

    <a-alert
      type="info"
      message="上传 Excel 导入账号池，支持查看失败明细与模板下载。"
      style="margin-bottom: 20px;"
    />

    <a-space style="margin-bottom: 16px;" align="center">
      <a-upload
        accept=".xlsx,.xls"
        :show-upload-list="false"
        :custom-request="uploadWithProgress"
      >
        <a-button type="primary" :loading="submitting">
          {{ submitting ? "上传中..." : "选择并上传" }}
        </a-button>
      </a-upload>
      <a :href="'/api/v1/mobile-accounts/template'" target="_blank" rel="noopener">
        <a-button>下载模板 Excel</a-button>
      </a>
      <a-button @click="loadAccounts">刷新账号列表</a-button>
    </a-space>

    <a-progress
      v-if="submitting && uploadProgress > 0"
      :percent="uploadProgress"
      status="active"
      style="margin-bottom: 16px;"
    />

    <template v-if="importErrors.length">
      <a-divider>导入错误明细</a-divider>
      <a-table
        :columns="errorColumns"
        :data-source="importErrors"
        :row-key="(r, i) => `${r.row_no}-${r.field_name || 'none'}-${i}`"
        size="small"
        :pagination="{ current: errorPage, pageSize: errorPageSize, total: errorTotal, showTotal: t => `共 ${t} 条错误`, onChange: onErrorPageChange }"
        style="margin-bottom: 20px;"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'row_no'">
            {{ record.row_no === 0 ? "模板" : record.row_no }}
          </template>
        </template>
      </a-table>
    </template>

    <a-divider>账号列表</a-divider>
    <a-table
      :columns="accountColumns"
      :data-source="pagedAccounts"
      row-key="id"
      size="small"
      :pagination="{
        current: accountsPage,
        pageSize: accountsPageSize,
        total: accounts.length,
        showTotal: t => `共 ${t} 条账号`,
        onChange: (p) => { accountsPage = p; },
      }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="ACCOUNT_STATUS_COLOR[record.status]">{{ ACCOUNT_STATUS_LABEL[record.status] || record.status }}</a-tag>
        </template>
      </template>
    </a-table>
  </a-card>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { message } from "ant-design-vue";
import { apiFetch, reportGlobalError } from "../services/api";

const ACCOUNT_STATUS_COLOR = { available: "success", assigned: "processing", disabled: "default", expired: "warning" };
const ACCOUNT_STATUS_LABEL = { available: "可用", assigned: "已分配", disabled: "禁用", expired: "到期" };

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

const errorColumns = [
  { title: "行号", key: "row_no", width: 70 },
  { title: "字段", dataIndex: "field_name", customRender: ({ text }) => text || "-" },
  { title: "错误码", dataIndex: "error_code" },
  { title: "说明", dataIndex: "error_message" },
];

const accountColumns = [
  { title: "ID", dataIndex: "id", width: 70 },
  { title: "账号", dataIndex: "account" },
  { title: "状态", dataIndex: "status", key: "status", width: 100 },
  { title: "批次", dataIndex: "batch_code" },
  { title: "类型", dataIndex: "batch_type" },
];

async function onErrorPageChange(p) {
  errorPage.value = p;
  if (currentImportJobId.value) {
    await loadImportErrors(currentImportJobId.value, p);
  }
}

async function loadAccounts() {
  const payload = await apiFetch("/api/v1/mobile-accounts");
  accounts.value = payload.data.items;
  accountsPage.value = 1;
}

async function loadImportErrors(jobId, pg = 1) {
  if (!jobId) return;
  const payload = await apiFetch(`/api/v1/imports/${jobId}?page=${pg}&page_size=${errorPageSize}`);
  importErrors.value = payload.data.errors.items;
  errorTotal.value = payload.data.errors.total;
  errorPage.value = payload.data.errors.page;
  currentImportJobId.value = jobId;
}

async function uploadWithProgress({ file, onProgress, onSuccess, onError }) {
  submitting.value = true;
  uploadProgress.value = 0;
  importErrors.value = [];
  errorTotal.value = 0;
  errorPage.value = 1;
  currentImportJobId.value = null;
  try {
    const payload = await doXhrUpload(file, (percent) => {
      uploadProgress.value = percent;
      onProgress({ percent });
    });
    onSuccess(payload);
    message.success(`导入完成：成功 ${payload.data.success_rows} 行，失败 ${payload.data.failed_rows} 行`);
    if (payload.data.failed_rows > 0) {
      await loadImportErrors(payload.data.job_id, 1);
    }
    await loadAccounts();
  } catch (error) {
    onError(error);
    message.error(error.message || "账号导入失败");
    importErrors.value = Array.isArray(error.details) ? error.details : [];
    errorTotal.value = importErrors.value.length;
  } finally {
    submitting.value = false;
    uploadProgress.value = 0;
  }
}

function doXhrUpload(file, onProgress) {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append("file", file);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/v1/mobile-accounts/import");
    xhr.withCredentials = true;
    const csrfToken = sessionStorage.getItem("csrf_token") || "";
    if (csrfToken) xhr.setRequestHeader("X-CSRF-Token", csrfToken);
    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable) return;
      onProgress(Math.min(100, Math.max(0, Math.round((event.loaded / event.total) * 100))));
    };
    xhr.onload = () => {
      const contentType = xhr.getResponseHeader("content-type") || "";
      let payload = null;
      if (contentType.includes("application/json")) {
        try { payload = JSON.parse(xhr.responseText); } catch (_) { payload = null; }
      }
      if (xhr.status >= 200 && xhr.status < 300) { resolve(payload); return; }
      const fallbackMessage = xhr.status === 413 ? "上传文件过大，请压缩后重试（当前上限 64MB）" : "请求失败";
      const err = new Error(payload?.message || fallbackMessage);
      err.code = payload?.code || "REQUEST_FAILED";
      err.details = payload?.details || [];
      reportGlobalError({ path: "/api/v1/mobile-accounts/import", method: "POST", status: xhr.status, code: err.code, message: err.message, details: err.details });
      reject(err);
    };
    xhr.onerror = () => {
      const err = new Error("网络异常，请稍后重试");
      err.code = "NETWORK_ERROR";
      reportGlobalError({ path: "/api/v1/mobile-accounts/import", method: "POST", code: err.code, message: err.message });
      reject(err);
    };
    xhr.send(formData);
  });
}

onMounted(loadAccounts);
</script>

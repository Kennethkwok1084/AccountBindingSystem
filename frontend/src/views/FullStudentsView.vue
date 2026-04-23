<template>
  <a-card :bordered="false">
    <template #title>完整名单导入</template>

    <a-space style="margin-bottom: 16px;" align="center">
      <a-upload accept=".xlsx,.xls" :show-upload-list="false" :before-upload="captureFile">
        <a-button>选择文件</a-button>
      </a-upload>
      <span v-if="selectedFile" style="color: #52c41a;">已选：{{ selectedFile.name }}</span>
      <a-button type="primary" :loading="previewing" :disabled="!selectedFile || executing" @click="submitAndConfirm">
        {{ previewing ? "预览中..." : executing ? "执行中..." : "执行" }}
      </a-button>
      <a-button @click="loadStudents">刷新用户列表</a-button>
    </a-space>

    <a-progress
      v-if="progress.visible"
      :percent="Number(progress.progressPercent.toFixed(1))"
      status="active"
      style="margin-bottom: 12px;"
    />
    <p v-if="progress.visible" style="color: #8c8c8c; margin-bottom: 16px;">
      批次 {{ progress.operationBatchId }}：{{ progress.processedRows }} / {{ progress.totalRows }}
    </p>

    <a-modal
      v-model:open="confirmVisible"
      title="执行前预览"
      :width="760"
      :ok-text="executing ? '执行中...' : '确认执行'"
      cancel-text="取消"
      :confirm-loading="executing"
      @ok="executeConfirmed"
      @cancel="closeConfirm"
    >
      <template v-if="previewData">
        <a-descriptions bordered size="small" style="margin-bottom: 12px;">
          <a-descriptions-item label="任务 ID">{{ previewData.job_id }}</a-descriptions-item>
          <a-descriptions-item label="释放">{{ previewData.release_count }}</a-descriptions-item>
          <a-descriptions-item label="冲突">
            <a-tag :color="previewData.conflict_count > 0 ? 'warning' : 'default'">{{ previewData.conflict_count }}</a-tag>
          </a-descriptions-item>
        </a-descriptions>
        <a-list
          :data-source="previewRows"
          size="small"
          :pagination="false"
          bordered
          style="max-height: 360px; overflow-y: auto;"
        >
          <template #renderItem="{ item }">
            <a-list-item>
              <a-space>
                <span>{{ item.student_no }}</span>
                <span>{{ item.name }}</span>
                <span>{{ item.expire_at }}</span>
                <a-tag v-if="item.conflict" color="warning">冲突</a-tag>
              </a-space>
            </a-list-item>
          </template>
        </a-list>
        <p v-if="previewData.preview.length > 20" style="color: #8c8c8c; margin-top: 8px;">
          仅展示前 20 条，确认后将执行全部预览数据。
        </p>
      </template>
    </a-modal>

    <a-divider>学生列表</a-divider>

    <a-form layout="inline" style="margin-bottom: 16px; flex-wrap: wrap; gap: 8px;">
      <a-form-item label="学号/姓名">
        <a-input v-model:value="studentFilters.keyword" placeholder="输入学号或姓名" allow-clear style="width: 180px;" />
      </a-form-item>
      <a-form-item label="绑定状态">
        <a-select v-model:value="studentFilters.hasBinding" style="width: 120px;">
          <a-select-option value="">全部</a-select-option>
          <a-select-option value="true">已绑定</a-select-option>
          <a-select-option value="false">未绑定</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item>
        <a-space>
          <a-button type="primary" @click="loadStudents">查询</a-button>
          <a-button @click="resetStudentFilters">重置</a-button>
        </a-space>
      </a-form-item>
    </a-form>

    <a-table
      :columns="columns"
      :data-source="students"
      row-key="id"
      :pagination="pagination"
      @change="tableChange"
      :scroll="{ x: 'max-content' }"
    />
  </a-card>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { message } from "ant-design-vue";
import { apiFetch, createIdempotencyKey } from "../services/api";

const selectedFile = ref(null);
const previewData = ref(null);
const confirmVisible = ref(false);
const executing = ref(false);
const previewing = ref(false);
const students = ref([]);
const studentsPage = ref(1);
const studentsPageSize = ref(20);
const studentsTotal = ref(0);
const studentSortBy = ref("id");
const studentSortOrder = ref("asc");
const studentFilters = ref({ keyword: "", hasBinding: "" });
const progress = ref({ visible: false, operationBatchId: null, totalRows: 0, processedRows: 0, progressPercent: 0 });
let pollTimer = null;

const previewRows = computed(() => previewData.value?.preview?.slice(0, 20) || []);

const pagination = computed(() => ({
  current: studentsPage.value,
  pageSize: studentsPageSize.value,
  total: studentsTotal.value,
  showTotal: (t) => `共 ${t} 条用户`,
  showSizeChanger: false,
}));

const columns = computed(() => [
  { title: "ID", dataIndex: "id", sorter: true, sortOrder: studentSortBy.value === "id" ? (studentSortOrder.value === "desc" ? "descend" : "ascend") : null, width: 70 },
  { title: "学号", dataIndex: "student_no", sorter: true, sortOrder: studentSortBy.value === "student_no" ? (studentSortOrder.value === "desc" ? "descend" : "ascend") : null },
  { title: "姓名", dataIndex: "name", sorter: true, sortOrder: studentSortBy.value === "name" ? (studentSortOrder.value === "desc" ? "descend" : "ascend") : null, customRender: ({ text }) => text || "-" },
  { title: "当前移动账号", dataIndex: "current_mobile_account", sorter: true, sortOrder: studentSortBy.value === "current_mobile_account" ? (studentSortOrder.value === "desc" ? "descend" : "ascend") : null, customRender: ({ text }) => text || "-" },
  { title: "绑定到期", dataIndex: "current_binding_expire_at", sorter: true, sortOrder: studentSortBy.value === "current_binding_expire_at" ? (studentSortOrder.value === "desc" ? "descend" : "ascend") : null, customRender: ({ text }) => text || "-" },
  { title: "来源到期", dataIndex: "source_expire_at", sorter: true, sortOrder: studentSortBy.value === "source_expire_at" ? (studentSortOrder.value === "desc" ? "descend" : "ascend") : null, customRender: ({ text }) => text || "-" },
]);

function tableChange(pag, _filters, sorter) {
  const s = Array.isArray(sorter) ? sorter[0] : sorter;
  if (s && s.field) {
    studentSortBy.value = s.field;
    studentSortOrder.value = s.order === "descend" ? "desc" : "asc";
  }
  studentsPage.value = pag.current;
  studentsPageSize.value = pag.pageSize;
  loadStudents();
}

function captureFile(file) {
  selectedFile.value = file;
  return false;
}

async function submitAndConfirm() {
  if (!selectedFile.value) return;
  previewing.value = true;
  try {
    const formData = new FormData();
    formData.append("file", selectedFile.value);
    const payload = await apiFetch("/api/v1/full-students/import/preview", { method: "POST", body: formData });
    previewData.value = payload.data;
    confirmVisible.value = true;
  } catch (error) {
    message.error(error.message || "生成预览失败");
    previewData.value = null;
  } finally {
    previewing.value = false;
  }
}

function closeConfirm() {
  confirmVisible.value = false;
  previewData.value = null;
}

async function loadStudents() {
  const params = new URLSearchParams({
    page: String(studentsPage.value),
    page_size: String(studentsPageSize.value),
    sort_by: studentSortBy.value,
    sort_order: studentSortOrder.value,
  });
  if (studentFilters.value.keyword) params.set("keyword", studentFilters.value.keyword);
  if (studentFilters.value.hasBinding) params.set("has_binding", studentFilters.value.hasBinding);
  const payload = await apiFetch(`/api/v1/students?${params.toString()}`);
  students.value = payload.data.items || [];
  studentsTotal.value = payload.data.total || 0;
  studentsPage.value = payload.data.page || 1;
  studentsPageSize.value = payload.data.page_size || 20;
}

function resetStudentFilters() {
  studentFilters.value = { keyword: "", hasBinding: "" };
  studentsPage.value = 1;
  loadStudents();
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

async function pollExecution(operationBatchId) {
  try {
    const payload = await apiFetch(`/api/v1/operation-batches/${operationBatchId}`);
    const data = payload.data || {};
    progress.value = {
      visible: true,
      operationBatchId,
      totalRows: data.total_rows || 0,
      processedRows: data.processed_rows || 0,
      progressPercent: Math.max(0, Math.min(Number(data.progress_percent || 0), 100)),
    };
    if (data.status === "success" || data.status === "partial_success" || data.status === "failed") {
      stopPolling();
      executing.value = false;
      const releasedRows = Number(data.released_rows || 0);
      message.success(`执行完成：成功 ${data.success_rows || 0}，失败 ${data.failed_rows || 0}` + (releasedRows > 0 ? `，释放 ${releasedRows}` : ""));
      await loadStudents();
      selectedFile.value = null;
      previewData.value = null;
      confirmVisible.value = false;
    }
  } catch (error) {
    stopPolling();
    executing.value = false;
    message.error(error.message || "查询执行进度失败");
  }
}

async function executeConfirmed() {
  if (!previewData.value) return;
  executing.value = true;
  try {
    const payload = await apiFetch(`/api/v1/full-students/import/${previewData.value.job_id}/execute-async`, {
      method: "POST",
      headers: { "X-Idempotency-Key": createIdempotencyKey("full-students") },
      body: JSON.stringify({ confirm: true }),
    });
    const operationBatchId = payload.data.operation_batch_id;
    message.info(payload.data.started ? "任务已启动，正在后台执行..." : "任务正在执行中，正在刷新进度...");
    stopPolling();
    pollExecution(operationBatchId);
    pollTimer = setInterval(() => pollExecution(operationBatchId), 2000);
  } catch (error) {
    executing.value = false;
    message.error(error.message || "启动执行失败");
  } finally {
    confirmVisible.value = false;
  }
}

onBeforeUnmount(stopPolling);
onMounted(loadStudents);
watch(studentsPage, () => loadStudents());
</script>

<template>
  <a-card :bordered="false">
    <template #title>收费清单执行</template>

    <a-alert
      type="info"
      message="点击执行后会弹窗展示预览，确认后才会真正写入。"
      style="margin-bottom: 20px;"
    />

    <a-space style="margin-bottom: 16px;" align="center">
      <a-upload
        accept=".xlsx,.xls"
        :show-upload-list="false"
        :before-upload="captureFile"
      >
        <a-button>选择文件</a-button>
      </a-upload>
      <span v-if="selectedFile" style="color: #52c41a;">已选：{{ selectedFile.name }}</span>
      <a-button
        type="primary"
        :loading="previewing"
        :disabled="!selectedFile || executing"
        @click="submitAndConfirm"
      >
        {{ previewing ? "预览中..." : "执行" }}
      </a-button>
    </a-space>

    <template v-if="importErrors.length">
      <a-alert
        type="error"
        :message="`导入错误明细（${importErrors.length} 条）`"
        style="margin-bottom: 16px;"
      />
      <a-table
        :columns="errorColumns"
        :data-source="importErrors"
        :row-key="(r, i) => `${r.row_no}-${r.field_name || 'none'}-${i}`"
        size="small"
        :pagination="false"
        style="margin-bottom: 20px;"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'row_no'">
            {{ record.row_no === 0 ? "模板" : record.row_no }}
          </template>
        </template>
      </a-table>
    </template>

    <a-modal
      v-model:open="confirmVisible"
      title="执行前预览"
      :width="960"
      :ok-text="executing ? '执行中...' : '确认执行'"
      cancel-text="取消"
      :confirm-loading="executing"
      :ok-button-props="{ disabled: executing }"
      @ok="executeConfirmed"
      @cancel="closeConfirm"
    >
      <template v-if="previewData">
        <a-descriptions bordered size="small" style="margin-bottom: 12px;">
          <a-descriptions-item label="批次 ID">{{ previewData.operation_batch_id }}</a-descriptions-item>
          <a-descriptions-item label="新分配">{{ previewData.to_allocate_count }}</a-descriptions-item>
          <a-descriptions-item label="续费">{{ previewData.to_renew_count }}</a-descriptions-item>
          <a-descriptions-item label="换绑">{{ previewData.to_rebind_count }}</a-descriptions-item>
          <a-descriptions-item label="失败">
            <a-tag :color="previewData.fail_count > 0 ? 'error' : 'default'">{{ previewData.fail_count }}</a-tag>
          </a-descriptions-item>
        </a-descriptions>
        <a-table
          :columns="previewColumns"
          :data-source="previewRows"
          row-key="row_no"
          size="small"
          :pagination="false"
          :scroll="{ y: 360 }"
        />
        <p v-if="previewData.details.length > 20" style="color: #8c8c8c; margin-top: 8px;">
          仅展示前 20 条，确认后将执行全部预览数据。
        </p>
      </template>
    </a-modal>
  </a-card>
</template>

<script setup>
import { computed, ref } from "vue";
import { apiFetch, createIdempotencyKey } from "../services/api";
import { useLeaveGuard } from "../composables/useLeaveGuard";
import { message } from "ant-design-vue";

const selectedFile = ref(null);
const previewData = ref(null);
const confirmVisible = ref(false);
const executing = ref(false);
const previewing = ref(false);
const importErrors = ref([]);

const hasPendingPreview = computed(() => Boolean(selectedFile.value || previewData.value));
const previewRows = computed(() => previewData.value?.details?.slice(0, 20) || []);

useLeaveGuard(hasPendingPreview, "收费清单已经选择或生成预览，离开后需要重新上传，确定离开吗？");

function captureFile(file) {
  selectedFile.value = file;
  return false;
}

const errorColumns = [
  { title: "行号", dataIndex: "row_no", key: "row_no", width: 70 },
  { title: "字段", dataIndex: "field_name", customRender: ({ text }) => text || "-" },
  { title: "错误码", dataIndex: "error_code" },
  { title: "说明", dataIndex: "error_message" },
];

const previewColumns = [
  { title: "行号", dataIndex: "row_no", width: 70 },
  { title: "学号", dataIndex: "student_no" },
  { title: "姓名", dataIndex: "name" },
  { title: "动作", dataIndex: "action_plan" },
  { title: "说明", dataIndex: "result_message" },
];

async function submitAndConfirm() {
  if (!selectedFile.value) return;
  importErrors.value = [];
  previewing.value = true;
  try {
    const formData = new FormData();
    formData.append("file", selectedFile.value);
    const payload = await apiFetch("/api/v1/charge-batches/preview", {
      method: "POST",
      body: formData,
    });
    previewData.value = payload.data;
    importErrors.value = Array.isArray(payload.data.import_errors) ? payload.data.import_errors : [];
    confirmVisible.value = true;
  } catch (error) {
    message.error(error.message || "生成预览失败");
    importErrors.value = Array.isArray(error.details) ? error.details : [];
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
  if (!previewData.value) return;
  executing.value = true;
  try {
    const payload = await apiFetch(`/api/v1/charge-batches/${previewData.value.operation_batch_id}/execute`, {
      method: "POST",
      headers: { "X-Idempotency-Key": createIdempotencyKey("charge") },
      body: JSON.stringify({ confirm: true }),
    });
    message.success(`执行完成：成功 ${payload.data.success_count}，失败 ${payload.data.fail_count}`);
    selectedFile.value = null;
    previewData.value = null;
    confirmVisible.value = false;
  } finally {
    executing.value = false;
  }
}
</script>

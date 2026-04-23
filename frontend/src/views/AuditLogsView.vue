<template>
  <a-card :bordered="false">
    <template #title>审计日志</template>
    <template #extra>
      <a-space>
        <a-button :loading="exporting" @click="exportLogs">导出 Excel</a-button>
        <a-button @click="load">刷新</a-button>
      </a-space>
    </template>

    <a-form layout="inline" style="margin-bottom: 16px; flex-wrap: wrap; gap: 8px;">
      <a-form-item label="关键字">
        <a-input v-model:value="filters.keyword" placeholder="动作/资源类型/资源ID" allow-clear style="width: 180px;" />
      </a-form-item>
      <a-form-item label="动作">
        <a-input v-model:value="filters.action" placeholder="如 manual_rebind" allow-clear style="width: 160px;" />
      </a-form-item>
      <a-form-item label="资源类型">
        <a-input v-model:value="filters.resourceType" placeholder="如 student" allow-clear style="width: 130px;" />
      </a-form-item>
      <a-form-item label="资源 ID">
        <a-input v-model:value="filters.resourceId" placeholder="如 10001" allow-clear style="width: 120px;" />
      </a-form-item>
      <a-form-item label="时间范围">
        <a-range-picker
          v-model:value="dateRange"
          value-format="YYYY-MM-DD"
          style="width: 240px;"
        />
      </a-form-item>
      <a-form-item>
        <a-space>
          <a-button type="primary" @click="applyFilters">查询</a-button>
          <a-button @click="resetFilters">重置</a-button>
        </a-space>
      </a-form-item>
    </a-form>

    <a-alert v-if="exportState" type="success" message="审计日志导出已生成" show-icon style="margin-bottom: 12px;">
      <template #description>
        已生成文件 {{ exportState.filename }}，共 {{ exportState.rowCount }} 条。请前往导出记录下载。
        <div style="margin-top: 12px;">
          <a-button type="primary" size="small" @click="goToExports">前往导出记录</a-button>
        </div>
      </template>
    </a-alert>

    <a-table
      :columns="columns"
      :data-source="items"
      row-key="id"
      :pagination="pagination"
      @change="tableChange"
      :scroll="{ x: 'max-content' }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'detail_json'">
          <pre class="compact-json">{{ formatDetail(record.detail_json) }}</pre>
        </template>
      </template>
    </a-table>
  </a-card>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { apiFetch } from "../services/api";

const router = useRouter();
const filters = reactive({ keyword: "", action: "", resourceType: "", resourceId: "" });
const dateRange = ref([]);
const items = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const sortBy = ref("created_at");
const sortOrder = ref("desc");
const exporting = ref(false);
const exportState = ref(null);

const pagination = computed(() => ({
  current: page.value,
  pageSize: pageSize.value,
  total: total.value,
  showTotal: (t) => `共 ${t} 条`,
  showSizeChanger: false,
}));

const columns = computed(() => [
  { title: "ID", dataIndex: "id", sorter: true, sortOrder: sortBy.value === "id" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null, width: 70 },
  { title: "动作", dataIndex: "action", sorter: true, sortOrder: sortBy.value === "action" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null },
  { title: "资源类型", dataIndex: "resource_type", sorter: true, sortOrder: sortBy.value === "resource_type" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null },
  { title: "资源 ID", dataIndex: "resource_id", sorter: true, sortOrder: sortBy.value === "resource_id" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null, customRender: ({ text }) => text || "-" },
  { title: "操作人", dataIndex: "operator_id", customRender: ({ text }) => text || "-" },
  { title: "详情", dataIndex: "detail_json", key: "detail_json" },
  { title: "时间", dataIndex: "created_at", sorter: true, sortOrder: sortBy.value === "created_at" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null },
]);

function tableChange(pag, _filters, sorter) {
  const s = Array.isArray(sorter) ? sorter[0] : sorter;
  if (s && s.field) {
    sortBy.value = s.field;
    sortOrder.value = s.order === "descend" ? "desc" : "asc";
  }
  page.value = pag.current;
  pageSize.value = pag.pageSize;
  load();
}

function applyFilters() {
  page.value = 1;
  load();
}

function resetFilters() {
  filters.keyword = "";
  filters.action = "";
  filters.resourceType = "";
  filters.resourceId = "";
  dateRange.value = [];
  page.value = 1;
  load();
}

function formatDetail(detail) {
  if (!detail || Object.keys(detail).length === 0) return "-";
  return JSON.stringify(detail, null, 2);
}

async function load() {
  const params = new URLSearchParams({
    page: String(page.value),
    page_size: String(pageSize.value),
    sort_by: sortBy.value,
    sort_order: sortOrder.value,
  });
  if (filters.keyword) params.set("keyword", filters.keyword);
  if (filters.action) params.set("action", filters.action);
  if (filters.resourceType) params.set("resource_type", filters.resourceType);
  if (filters.resourceId) params.set("resource_id", filters.resourceId);
  if (dateRange.value?.[0]) params.set("created_from", dateRange.value[0]);
  if (dateRange.value?.[1]) params.set("created_to", dateRange.value[1]);
  const payload = await apiFetch(`/api/v1/audit-logs?${params.toString()}`);
  items.value = payload.data.items || [];
  total.value = payload.data.total || 0;
  page.value = payload.data.page || 1;
  pageSize.value = payload.data.page_size || 20;
}

async function exportLogs() {
  exporting.value = true;
  exportState.value = null;
  try {
    const payload = await apiFetch("/api/v1/audit-logs/export", {
      method: "POST",
      body: JSON.stringify({
        keyword: filters.keyword,
        action: filters.action,
        resource_type: filters.resourceType,
        resource_id: filters.resourceId,
        created_from: dateRange.value?.[0] || "",
        created_to: dateRange.value?.[1] || "",
        sort_by: sortBy.value,
        sort_order: sortOrder.value,
      }),
    });
    exportState.value = {
      filename: payload.data.export_job.filename,
      rowCount: payload.data.export_job.row_count,
    };
  } finally {
    exporting.value = false;
  }
}

function goToExports() {
  router.push({ path: "/exports", query: { keyword: exportState.value?.filename || "" } });
}

onMounted(load);
</script>

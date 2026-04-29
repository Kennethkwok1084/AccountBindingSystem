<template>
  <a-card :bordered="false">
    <template #title>收费归档</template>
    <template #extra>
      <a-space>
        <a-button :loading="importsLoading" @click="loadImports">刷新批次</a-button>
        <a-button :loading="recordsLoading" @click="loadRecords">刷新记录</a-button>
      </a-space>
    </template>

    <a-alert
      type="info"
      show-icon
      style="margin-bottom: 16px;"
      message="收费清单上传后会由后台自动归档"
      description="这里用于查看已归档的原始收费记录，并按筛选条件导出合并结果。"
    />

    <a-form layout="inline" style="margin-bottom: 16px; flex-wrap: wrap; gap: 8px;">
      <a-form-item label="月份">
        <a-date-picker
          v-model:value="filters.sourceMonth"
          picker="month"
          value-format="YYYY-MM"
          allow-clear
          style="width: 140px;"
        />
      </a-form-item>
      <a-form-item label="收费时间">
        <a-range-picker
          v-model:value="filters.chargeTimeRange"
          value-format="YYYY-MM-DD"
          style="width: 240px;"
        />
      </a-form-item>
      <a-form-item label="批次ID">
        <a-input-number v-model:value="filters.importJobId" :min="1" allow-clear style="width: 110px;" />
      </a-form-item>
      <a-form-item label="关键字">
        <a-input v-model:value="filters.keyword" allow-clear style="width: 180px;" />
      </a-form-item>
      <a-form-item>
        <a-space>
          <a-button type="primary" :loading="recordsLoading" @click="searchRecords">查询</a-button>
          <a-button @click="resetFilters">重置</a-button>
          <a-button :loading="exporting" @click="exportRecords">导出合并</a-button>
        </a-space>
      </a-form-item>
    </a-form>

    <a-tabs>
      <a-tab-pane key="records" tab="归档记录">
        <a-table
          :columns="recordColumns"
          :data-source="records"
          row-key="id"
          size="small"
          :pagination="recordPagination"
          :loading="recordsLoading"
          :scroll="{ x: 'max-content' }"
          @change="handleRecordTableChange"
        />
      </a-tab-pane>
      <a-tab-pane key="imports" tab="导入批次">
        <a-table
          :columns="importColumns"
          :data-source="imports"
          row-key="id"
          size="small"
          :pagination="importPagination"
          :loading="importsLoading"
          @change="handleImportTableChange"
        />
      </a-tab-pane>
    </a-tabs>
  </a-card>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { message } from "ant-design-vue";
import { apiFetch } from "../services/api";

const router = useRouter();

const exporting = ref(false);
const recordsLoading = ref(false);
const importsLoading = ref(false);
const records = ref([]);
const imports = ref([]);
const recordPage = ref(1);
const recordPageSize = ref(50);
const recordTotal = ref(0);
const importPage = ref(1);
const importPageSize = ref(20);
const importTotal = ref(0);

const filters = reactive({
  sourceMonth: "",
  chargeTimeRange: [],
  importJobId: null,
  keyword: "",
});

const rawColumns = computed(() => {
  const seen = new Set();
  const columns = [];
  for (const row of records.value) {
    const raw = row.raw_data || {};
    for (const key of Object.keys(raw)) {
      if (!seen.has(key)) {
        seen.add(key);
        columns.push(key);
      }
    }
  }
  return columns;
});

const recordColumns = computed(() => [
  { title: "收费时间", dataIndex: "parsed_charge_time", customRender: ({ text }) => text || "-" },
  { title: "月份", dataIndex: "source_month", customRender: ({ text }) => text || "-" },
  { title: "批次ID", dataIndex: "import_job_id", width: 90 },
  { title: "行号", dataIndex: "row_no", width: 70 },
  { title: "源文件", dataIndex: "original_filename" },
  ...rawColumns.value.map((column) => ({
    title: column,
    key: `raw-${column}`,
    customRender: ({ record }) => formatCell(record.raw_data?.[column]),
  })),
]);

const importColumns = [
  { title: "批次ID", dataIndex: "id", width: 90 },
  { title: "文件名", dataIndex: "original_filename" },
  { title: "状态", dataIndex: "status", width: 120 },
  { title: "行数", dataIndex: "total_rows", width: 90 },
  { title: "无效时间", dataIndex: "invalid_time_rows", width: 100 },
  { title: "月份", key: "source_months", customRender: ({ record }) => formatMonths(record.source_months) },
  { title: "导入时间", dataIndex: "created_at" },
];

const recordPagination = computed(() => ({
  current: recordPage.value,
  pageSize: recordPageSize.value,
  total: recordTotal.value,
  showTotal: (total) => `共 ${total} 条`,
  showSizeChanger: false,
}));

const importPagination = computed(() => ({
  current: importPage.value,
  pageSize: importPageSize.value,
  total: importTotal.value,
  showTotal: (total) => `共 ${total} 个批次`,
  showSizeChanger: false,
}));

function formatMonths(months) {
  return Array.isArray(months) && months.length ? months.join(", ") : "-";
}

function formatCell(value) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function buildFilters() {
  const params = {};
  if (filters.sourceMonth) params.source_month = filters.sourceMonth;
  if (filters.importJobId) params.import_job_id = filters.importJobId;
  if (filters.keyword) params.keyword = filters.keyword;
  if (filters.chargeTimeRange?.[0]) params.charge_time_from = filters.chargeTimeRange[0];
  if (filters.chargeTimeRange?.[1]) params.charge_time_to = filters.chargeTimeRange[1];
  return params;
}

function toQuery(params) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") search.set(key, value);
  });
  return search.toString();
}

async function loadImports() {
  importsLoading.value = true;
  try {
    const query = toQuery({ page: importPage.value, page_size: importPageSize.value });
    const payload = await apiFetch(`/api/v1/charge-record-imports?${query}`);
    imports.value = payload.data.items || [];
    importTotal.value = payload.data.total || 0;
  } finally {
    importsLoading.value = false;
  }
}

async function loadRecords() {
  recordsLoading.value = true;
  try {
    const query = toQuery({ ...buildFilters(), page: recordPage.value, page_size: recordPageSize.value });
    const payload = await apiFetch(`/api/v1/charge-records?${query}`);
    records.value = payload.data.items || [];
    recordTotal.value = payload.data.total || 0;
  } finally {
    recordsLoading.value = false;
  }
}

function searchRecords() {
  recordPage.value = 1;
  loadRecords();
}

function resetFilters() {
  filters.sourceMonth = "";
  filters.chargeTimeRange = [];
  filters.importJobId = null;
  filters.keyword = "";
  recordPage.value = 1;
  loadRecords();
}

async function exportRecords() {
  exporting.value = true;
  try {
    const payload = await apiFetch("/api/v1/charge-records/export", {
      method: "POST",
      body: JSON.stringify(buildFilters()),
    });
    message.success(`导出已生成：${payload.data.export_job.filename}`);
    router.push({ path: "/exports", query: { export_id: payload.data.export_job.id } });
  } finally {
    exporting.value = false;
  }
}

function handleRecordTableChange(pagination) {
  recordPage.value = pagination.current;
  recordPageSize.value = pagination.pageSize;
  loadRecords();
}

function handleImportTableChange(pagination) {
  importPage.value = pagination.current;
  importPageSize.value = pagination.pageSize;
  loadImports();
}

onMounted(() => {
  loadImports();
  loadRecords();
});
</script>

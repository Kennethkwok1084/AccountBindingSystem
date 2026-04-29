<template>
  <a-space direction="vertical" size="large" style="width: 100%;">
    <a-card :bordered="false">
      <template #title>导出记录</template>
      <template #extra>
        <a-button :loading="loading" @click="load">刷新</a-button>
      </template>

      <a-form layout="inline" style="margin-bottom: 16px; flex-wrap: wrap; gap: 8px;">
        <a-form-item label="文件名关键字">
          <a-input v-model:value="filters.keyword" placeholder="如 移动" allow-clear style="width: 180px;" />
        </a-form-item>
        <a-form-item label="创建时间">
          <a-range-picker
            v-model:value="dateRange"
            value-format="YYYY-MM-DD"
            style="width: 240px;"
          />
        </a-form-item>
        <a-form-item>
          <a-space>
            <a-button type="primary" :loading="loading" @click="applyFilters">查询</a-button>
            <a-button @click="resetFilters">重置</a-button>
          </a-space>
        </a-form-item>
      </a-form>

      <a-alert
        v-if="message"
        :type="messageType"
        :message="message"
        show-icon
        style="margin-bottom: 12px;"
      />

      <a-table
        :columns="columns"
        :data-source="exports"
        row-key="id"
        :pagination="pagination"
        :loading="loading"
        :locale="{ emptyText: emptyText }"
        @change="tableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'download'">
            <a :href="`/api/v1/exports/${record.id}/download`" target="_blank" rel="noopener">
              <a-button type="link" size="small">下载</a-button>
            </a>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-card :bordered="false">
      <template #title>上传文件归档</template>
      <template #extra>
        <a-button :loading="archiveLoading" @click="loadUploadArchives">刷新</a-button>
      </template>

      <a-alert
        v-if="archiveMessage"
        :type="archiveMessageType"
        :message="archiveMessage"
        show-icon
        style="margin-bottom: 12px;"
      />

      <a-table
        :columns="archiveColumns"
        :data-source="uploadArchives"
        row-key="month"
        :pagination="false"
        :loading="archiveLoading"
        :locale="{ emptyText: archiveEmptyText }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'categories'">
            <a-space wrap>
              <a-tag v-for="category in record.categories" :key="category.job_type">
                {{ category.label }} {{ category.count }}
              </a-tag>
            </a-space>
          </template>
          <template v-else-if="column.key === 'total_size'">
            {{ formatSize(record.total_size) }}
          </template>
          <template v-else-if="column.key === 'download'">
            <a :href="`/api/v1/upload-archives/${encodeURIComponent(record.month)}/download`" target="_blank" rel="noopener">
              <a-button type="link" size="small">打包下载</a-button>
            </a>
          </template>
        </template>
      </a-table>
    </a-card>
  </a-space>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { apiFetch } from "../services/api";

const route = useRoute();
const exports = ref([]);
const filters = reactive({ keyword: "", exportId: "" });
const dateRange = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const sortBy = ref("created_at");
const sortOrder = ref("desc");
const loading = ref(false);
const message = ref("");
const messageType = ref("info");
const uploadArchives = ref([]);
const archiveLoading = ref(false);
const archiveMessage = ref("");
const archiveMessageType = ref("info");

const pagination = computed(() => ({
  current: page.value,
  pageSize: pageSize.value,
  total: total.value,
  showTotal: (t) => `共 ${t} 条`,
  showSizeChanger: false,
}));

const columns = computed(() => [
  { title: "ID", dataIndex: "id", sorter: true, sortOrder: sortBy.value === "id" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null, width: 70 },
  { title: "文件名", dataIndex: "filename", sorter: true, sortOrder: sortBy.value === "filename" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null, ellipsis: true },
  { title: "行数", dataIndex: "row_count", sorter: true, sortOrder: sortBy.value === "row_count" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null, width: 100 },
  { title: "创建时间", dataIndex: "created_at", sorter: true, sortOrder: sortBy.value === "created_at" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null },
  { title: "操作", key: "download", width: 100 },
]);

const archiveColumns = [
  { title: "月份", dataIndex: "month", width: 140 },
  { title: "文件数", dataIndex: "file_count", width: 100 },
  { title: "大小", key: "total_size", width: 120 },
  { title: "类型", key: "categories" },
  { title: "缺失", dataIndex: "missing_count", width: 90 },
  { title: "操作", key: "download", width: 120 },
];

const emptyText = computed(() => {
  if (loading.value) return "加载中";
  if (filters.exportId || filters.keyword || dateRange.value?.length) return "当前筛选条件下没有导出记录";
  return "暂无导出记录";
});

const archiveEmptyText = computed(() => (archiveLoading.value ? "加载中" : "暂无上传文件归档"));

function syncRouteFilters() {
  filters.exportId = route.query.export_id ? String(route.query.export_id) : "";
  filters.keyword = route.query.keyword ? String(route.query.keyword) : "";
  page.value = 1;
}

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
  filters.exportId = "";
  dateRange.value = [];
  page.value = 1;
  load();
}

async function load() {
  message.value = "";
  loading.value = true;
  const params = new URLSearchParams({
    page: String(page.value),
    page_size: String(pageSize.value),
    sort_by: sortBy.value,
    sort_order: sortOrder.value,
  });
  if (filters.exportId) params.set("export_id", filters.exportId);
  if (filters.keyword) params.set("keyword", filters.keyword);
  if (dateRange.value?.[0]) params.set("created_from", dateRange.value[0]);
  if (dateRange.value?.[1]) params.set("created_to", dateRange.value[1]);
  try {
    const payload = await apiFetch(`/api/v1/exports?${params.toString()}`);
    exports.value = payload.data.items || [];
    total.value = payload.data.total || 0;
    page.value = payload.data.page || 1;
    pageSize.value = payload.data.page_size || 20;
    if (!exports.value.length) {
      message.value = emptyText.value;
      messageType.value = "info";
    }
  } catch (error) {
    exports.value = [];
    total.value = 0;
    message.value = error.message || "导出记录加载失败";
    messageType.value = "error";
  } finally {
    loading.value = false;
  }
}

async function loadUploadArchives() {
  archiveMessage.value = "";
  archiveLoading.value = true;
  try {
    const payload = await apiFetch("/api/v1/upload-archives");
    uploadArchives.value = payload.data.items || [];
    if (!uploadArchives.value.length) {
      archiveMessage.value = archiveEmptyText.value;
      archiveMessageType.value = "info";
    }
  } catch (error) {
    uploadArchives.value = [];
    archiveMessage.value = error.message || "上传文件归档加载失败";
    archiveMessageType.value = "error";
  } finally {
    archiveLoading.value = false;
  }
}

function formatSize(size) {
  const value = Number(size || 0);
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`;
  return `${(value / 1024 / 1024 / 1024).toFixed(1)} GB`;
}

onMounted(() => {
  syncRouteFilters();
  load();
  loadUploadArchives();
});

watch(
  () => [route.query.export_id, route.query.keyword],
  () => {
    syncRouteFilters();
    load();
  },
);
</script>

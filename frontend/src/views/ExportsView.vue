<template>
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

const emptyText = computed(() => {
  if (loading.value) return "加载中";
  if (filters.exportId || filters.keyword || dateRange.value?.length) return "当前筛选条件下没有导出记录";
  return "暂无导出记录";
});

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

onMounted(() => {
  syncRouteFilters();
  load();
});

watch(
  () => [route.query.export_id, route.query.keyword],
  () => {
    syncRouteFilters();
    load();
  },
);
</script>

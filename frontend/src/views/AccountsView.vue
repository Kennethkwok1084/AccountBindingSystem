<template>
  <a-card :bordered="false">
    <template #title>账号池管理</template>
    <template #extra>
      <a-button @click="load">刷新</a-button>
    </template>

    <a-form layout="inline" style="margin-bottom: 16px; flex-wrap: wrap; gap: 8px;">
      <a-form-item label="账号搜索">
        <a-input v-model:value="filters.account" placeholder="输入账号关键字" allow-clear style="width: 180px;" />
      </a-form-item>
      <a-form-item label="状态">
        <a-select v-model:value="filters.status" style="width: 120px;">
          <a-select-option value="">全部</a-select-option>
          <a-select-option value="available">可用</a-select-option>
          <a-select-option value="assigned">已分配</a-select-option>
          <a-select-option value="disabled">禁用</a-select-option>
          <a-select-option value="expired">到期</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item label="批次编码">
        <a-input v-model:value="filters.batchCode" placeholder="如 B202601" allow-clear style="width: 140px;" />
      </a-form-item>
      <a-form-item>
        <a-space>
          <a-button type="primary" @click="applyFilters">查询</a-button>
          <a-button @click="resetFilters">重置</a-button>
        </a-space>
      </a-form-item>
    </a-form>

    <a-table
      :columns="columns"
      :data-source="items"
      row-key="id"
      :pagination="pagination"
      @change="tableChange"
      :scroll="{ x: 'max-content' }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="STATUS_COLOR[record.status]">{{ STATUS_LABEL[record.status] || record.status }}</a-tag>
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button size="small" @click="selectAccount(record.id)">详情</a-button>
            <a-button v-if="record.status !== 'disabled'" size="small" danger @click="disableAccount(record.id)">禁用</a-button>
            <a-button v-else size="small" type="primary" @click="enableAccount(record.id)">恢复</a-button>
          </a-space>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="detailVisible"
      title="账号详情"
      :footer="null"
      :width="760"
      @cancel="closeDetail"
    >
      <template v-if="selected">
        <a-row :gutter="16">
          <a-col :span="12">
            <a-descriptions title="基本信息" :column="1" bordered size="small">
              <a-descriptions-item label="账号">{{ selected.account }}</a-descriptions-item>
              <a-descriptions-item label="状态">
                <a-tag :color="STATUS_COLOR[selected.status]">{{ STATUS_LABEL[selected.status] || selected.status }}</a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="禁用原因">{{ selected.disabled_reason || "-" }}</a-descriptions-item>
              <a-descriptions-item label="批次编码">{{ selected.batch.batch_code }}</a-descriptions-item>
              <a-descriptions-item label="批次名称">{{ selected.batch.batch_name }}</a-descriptions-item>
              <a-descriptions-item label="优先级">{{ selected.batch.priority }}</a-descriptions-item>
              <a-descriptions-item label="到期日">{{ selected.batch.expire_at || "-" }}</a-descriptions-item>
            </a-descriptions>
          </a-col>
          <a-col :span="12">
            <a-card title="账号历史" size="small">
              <a-list :data-source="history" size="small" :locale="{ emptyText: '暂无历史' }">
                <template #renderItem="{ item }">
                  <a-list-item style="font-size: 13px;">
                    {{ item.created_at }} / {{ getActionTypeLabel(item.action_type) }} / 学生 {{ item.student_id }}
                  </a-list-item>
                </template>
              </a-list>
            </a-card>
          </a-col>
        </a-row>
      </template>
    </a-modal>
  </a-card>
</template>

<script setup>
import { reactive, ref, onMounted, computed } from "vue";
import { message } from "ant-design-vue";
import { apiFetch } from "../services/api";
import { getActionTypeLabel } from "../utils/ledgerActionLabels";

const STATUS_COLOR = { available: "success", assigned: "processing", disabled: "default", expired: "warning" };
const STATUS_LABEL = { available: "可用", assigned: "已分配", disabled: "禁用", expired: "到期" };

const filters = reactive({ account: "", status: "", batchCode: "" });
const items = ref([]);
const selected = ref(null);
const history = ref([]);
const detailVisible = ref(false);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const sortBy = ref("id");
const sortOrder = ref("desc");

const pagination = computed(() => ({
  current: page.value,
  pageSize: pageSize.value,
  total: total.value,
  showTotal: (t) => `共 ${t} 条`,
  showSizeChanger: false,
}));

const columns = computed(() => [
  { title: "ID", dataIndex: "id", sorter: true, sortOrder: sortBy.value === "id" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null, width: 70 },
  { title: "账号", dataIndex: "account", sorter: true, sortOrder: sortBy.value === "account" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null },
  { title: "状态", dataIndex: "status", key: "status", sorter: true, sortOrder: sortBy.value === "status" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null, width: 100 },
  { title: "批次", dataIndex: "batch_code", sorter: true, sortOrder: sortBy.value === "batch_code" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null },
  { title: "最近分配", dataIndex: "last_assigned_at", sorter: true, sortOrder: sortBy.value === "last_assigned_at" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null, customRender: ({ text }) => text || "-" },
  { title: "操作", key: "action", width: 160, fixed: "right" },
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
  filters.account = "";
  filters.status = "";
  filters.batchCode = "";
  page.value = 1;
  load();
}

async function load() {
  const params = new URLSearchParams({
    page: String(page.value),
    page_size: String(pageSize.value),
    sort_by: sortBy.value,
    sort_order: sortOrder.value,
  });
  if (filters.account) params.set("account", filters.account);
  if (filters.status) params.set("status", filters.status);
  if (filters.batchCode) params.set("batch_code", filters.batchCode);
  const payload = await apiFetch(`/api/v1/mobile-accounts?${params.toString()}`);
  items.value = payload.data.items;
  total.value = payload.data.total || 0;
  page.value = payload.data.page || 1;
  pageSize.value = payload.data.page_size || 20;
}

async function selectAccount(accountId) {
  const [detail, historyPayload] = await Promise.all([
    apiFetch(`/api/v1/mobile-accounts/${accountId}`),
    apiFetch(`/api/v1/mobile-accounts/${accountId}/history`),
  ]);
  selected.value = detail.data;
  history.value = historyPayload.data.items;
  detailVisible.value = true;
}

function closeDetail() {
  detailVisible.value = false;
  selected.value = null;
  history.value = [];
}

async function disableAccount(accountId) {
  await apiFetch(`/api/v1/mobile-accounts/${accountId}/disable`, {
    method: "PATCH",
    body: JSON.stringify({ reason: "frontend_disable" }),
  });
  message.success(`账号 ${accountId} 已禁用`);
  await load();
}

async function enableAccount(accountId) {
  await apiFetch(`/api/v1/mobile-accounts/${accountId}/enable`, {
    method: "PATCH",
    body: JSON.stringify({}),
  });
  message.success(`账号 ${accountId} 已恢复`);
  await load();
}

onMounted(load);
</script>

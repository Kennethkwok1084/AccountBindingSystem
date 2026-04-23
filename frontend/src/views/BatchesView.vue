<template>
  <a-card :bordered="false">
    <template #title>批次管理</template>
    <template #extra>
      <a-button @click="load">刷新</a-button>
    </template>

    <a-alert
      type="info"
      message="状态说明：参与分配 = 手工状态为 active 且批次未到期；已过期 = 到期日早于今天；停用 = 手工停用，不参与分配。"
      style="margin-bottom: 16px;"
    />

    <a-card title="新建批次" size="small" style="margin-bottom: 20px;">
      <a-form layout="inline" :model="createForm" @finish="createBatch" style="flex-wrap: wrap; gap: 8px;">
        <a-form-item label="批次编码">
          <a-input v-model:value="createForm.batch_code" style="width: 130px;" />
        </a-form-item>
        <a-form-item label="批次名称">
          <a-input v-model:value="createForm.batch_name" style="width: 130px;" />
        </a-form-item>
        <a-form-item label="类型">
          <a-select v-model:value="createForm.batch_type" style="width: 120px;">
            <a-select-option value="normal">normal</a-select-option>
            <a-select-option value="free">free</a-select-option>
            <a-select-option value="recycle">recycle</a-select-option>
            <a-select-option value="special">special</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="优先级">
          <a-input-number v-model:value="createForm.priority" style="width: 90px;" />
        </a-form-item>
        <a-form-item label="预警天数">
          <a-input-number v-model:value="createForm.warn_days" :min="0" style="width: 90px;" />
        </a-form-item>
        <a-form-item label="到期日">
          <a-date-picker v-model:value="createExpireAt" value-format="YYYY-MM-DD" style="width: 140px;" />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" html-type="submit">创建批次</a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <a-form layout="inline" style="margin-bottom: 16px; flex-wrap: wrap; gap: 8px;">
      <a-form-item label="关键字">
        <a-input v-model:value="filters.keyword" placeholder="编码/名称" allow-clear style="width: 160px;" />
      </a-form-item>
      <a-form-item label="类型">
        <a-input v-model:value="filters.batchType" placeholder="如 normal" allow-clear style="width: 120px;" />
      </a-form-item>
      <a-form-item label="状态">
        <a-select v-model:value="filters.status" style="width: 110px;">
          <a-select-option value="">全部</a-select-option>
          <a-select-option value="active">参与分配</a-select-option>
          <a-select-option value="expired">已过期</a-select-option>
          <a-select-option value="inactive">停用</a-select-option>
        </a-select>
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
        <template v-if="column.key === 'batch_name'">
          <a-input v-if="editingId === record.id" v-model:value="editRow.batch_name" size="small" style="min-width: 100px;" />
          <span v-else>{{ record.batch_name }}</span>
        </template>
        <template v-if="column.key === 'batch_type'">
          <a-select v-if="editingId === record.id" v-model:value="editRow.batch_type" size="small" style="width: 110px;">
            <a-select-option value="normal">normal</a-select-option>
            <a-select-option value="free">free</a-select-option>
            <a-select-option value="recycle">recycle</a-select-option>
            <a-select-option value="special">special</a-select-option>
          </a-select>
          <span v-else>{{ record.batch_type }}</span>
        </template>
        <template v-if="column.key === 'priority'">
          <a-input-number v-if="editingId === record.id" v-model:value="editRow.priority" size="small" style="width: 80px;" />
          <span v-else>{{ record.priority }}</span>
        </template>
        <template v-if="column.key === 'warn_days'">
          <a-input-number v-if="editingId === record.id" v-model:value="editRow.warn_days" size="small" :min="0" style="width: 80px;" />
          <span v-else>{{ record.warn_days }}</span>
        </template>
        <template v-if="column.key === 'expire_at'">
          <a-date-picker v-if="editingId === record.id" v-model:value="editRow.expire_at" value-format="YYYY-MM-DD" size="small" style="width: 130px;" />
          <span v-else>{{ record.expire_at || "-" }}</span>
        </template>
        <template v-if="column.key === 'status'">
          <a-select v-if="editingId === record.id" v-model:value="editRow.status" size="small" style="width: 100px;">
            <a-select-option value="active">启用</a-select-option>
            <a-select-option value="inactive">停用</a-select-option>
          </a-select>
          <a-tag v-else :color="statusTagColor(record.status)">{{ statusLabel(record.status) }}</a-tag>
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <template v-if="editingId === record.id">
              <a-button size="small" type="primary" @click="saveEdit(record.id)">保存</a-button>
              <a-button size="small" @click="cancelEdit">取消</a-button>
            </template>
            <template v-else>
              <a-button size="small" @click="startEdit(record)">编辑</a-button>
            </template>
          </a-space>
        </template>
      </template>
    </a-table>
  </a-card>
</template>

<script setup>
import { reactive, ref, onMounted, computed } from "vue";
import { message } from "ant-design-vue";
import { apiFetch } from "../services/api";

const items = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const sortBy = ref("priority");
const sortOrder = ref("desc");
const editingId = ref(null);
const createExpireAt = ref(null);

const filters = reactive({ keyword: "", batchType: "", status: "" });
const createForm = reactive({ batch_code: "", batch_name: "", batch_type: "normal", priority: 100, warn_days: 1, expire_at: "" });
const editRow = reactive({ batch_name: "", batch_type: "", priority: null, warn_days: null, expire_at: "", status: "active" });

const pagination = computed(() => ({
  current: page.value,
  pageSize: pageSize.value,
  total: total.value,
  showTotal: (t) => `共 ${t} 条`,
  showSizeChanger: false,
}));

const columns = computed(() => [
  { title: "ID", dataIndex: "id", sorter: true, sortOrder: sortBy.value === "id" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null, width: 70 },
  { title: "编码", dataIndex: "batch_code", sorter: true, sortOrder: sortBy.value === "batch_code" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null },
  { title: "名称", key: "batch_name", sorter: true, sortOrder: sortBy.value === "batch_name" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null },
  { title: "类型", key: "batch_type", sorter: true, sortOrder: sortBy.value === "batch_type" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null },
  { title: "优先级", key: "priority", sorter: true, sortOrder: sortBy.value === "priority" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null, width: 90 },
  { title: "预警天数", key: "warn_days", sorter: true, sortOrder: sortBy.value === "warn_days" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null, width: 90 },
  { title: "到期日", key: "expire_at", sorter: true, sortOrder: sortBy.value === "expire_at" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null },
  { title: "状态", key: "status", sorter: true, sortOrder: sortBy.value === "status" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null, width: 100 },
  { title: "操作", key: "action", width: 130, fixed: "right" },
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

function applyFilters() { page.value = 1; load(); }

function resetFilters() {
  filters.keyword = "";
  filters.batchType = "";
  filters.status = "";
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
  if (filters.keyword) params.set("keyword", filters.keyword);
  if (filters.batchType) params.set("batch_type", filters.batchType);
  if (filters.status) params.set("status", filters.status);
  const payload = await apiFetch(`/api/v1/batches?${params.toString()}`);
  items.value = payload.data.items;
  total.value = payload.data.total || 0;
  page.value = payload.data.page || 1;
  pageSize.value = payload.data.page_size || 20;
}

async function createBatch() {
  await apiFetch("/api/v1/batches", {
    method: "POST",
    body: JSON.stringify({ ...createForm, expire_at: createExpireAt.value || null }),
  });
  message.success(`批次 ${createForm.batch_code} 已创建`);
  Object.assign(createForm, { batch_code: "", batch_name: "", batch_type: "normal", priority: 100, warn_days: 1 });
  createExpireAt.value = null;
  await load();
}

function statusLabel(status) {
  return (
    {
      active: "参与分配",
      expired: "已过期",
      inactive: "停用",
    }[status] || status
  );
}

function statusTagColor(status) {
  return (
    {
      active: "success",
      expired: "warning",
      inactive: "default",
    }[status] || "default"
  );
}

function startEdit(item) {
  editingId.value = item.id;
  Object.assign(editRow, {
    batch_name: item.batch_name,
    batch_type: item.batch_type,
    priority: item.priority,
    warn_days: item.warn_days,
    expire_at: item.expire_at || null,
    status: item.raw_status || item.status,
  });
}

function cancelEdit() { editingId.value = null; }

async function saveEdit(batchId) {
  await apiFetch(`/api/v1/batches/${batchId}`, {
    method: "PUT",
    body: JSON.stringify({
      batch_name: editRow.batch_name,
      batch_type: editRow.batch_type,
      priority: Number(editRow.priority),
      warn_days: Number(editRow.warn_days),
      expire_at: editRow.expire_at || null,
      status: editRow.status,
    }),
  });
  message.success(`批次 ${batchId} 已更新`);
  editingId.value = null;
  await load();
}

onMounted(load);
</script>

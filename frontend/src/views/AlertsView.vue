<template>
  <a-card :bordered="false">
    <template #title>预警中心</template>
    <template #extra>
      <a-button @click="load">刷新</a-button>
    </template>

    <a-form layout="inline" style="margin-bottom: 16px; flex-wrap: wrap; gap: 8px;">
      <a-form-item label="预警类型">
        <a-input v-model:value="filters.type" placeholder="inventory_low / batch_expire 等" allow-clear style="width: 200px;" />
      </a-form-item>
      <a-form-item label="处理状态">
        <a-select v-model:value="filters.isResolved" style="width: 120px;">
          <a-select-option value="">全部</a-select-option>
          <a-select-option value="false">未处理</a-select-option>
          <a-select-option value="true">已处理</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item label="级别">
        <a-input v-model:value="filters.level" placeholder="warning / critical" allow-clear style="width: 140px;" />
      </a-form-item>
      <a-form-item label="关键字">
        <a-input v-model:value="filters.keyword" placeholder="按标题或内容搜索" allow-clear style="width: 180px;" />
      </a-form-item>
      <a-form-item>
        <a-space>
          <a-button type="primary" @click="applyFilters">查询</a-button>
          <a-button @click="resetFilters">重置</a-button>
        </a-space>
      </a-form-item>
    </a-form>

    <a-card v-if="conflictGroups.length" title="完整名单冲突分组" size="small" style="margin-bottom: 16px;">
      <p style="color: #8c8c8c; margin-bottom: 12px;">按冲突类型聚合学号，可一键复制整组学号用于后续处理。</p>
      <a-table
        :columns="conflictColumns"
        :data-source="conflictGroups"
        row-key="conflict_reason"
        size="small"
        :pagination="false"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'students'">
            <div class="group-students">{{ record.student_nos.join("、") || "-" }}</div>
          </template>
          <template v-if="column.key === 'action'">
            <a-button size="small" @click="copyStudents(record)">复制学号</a-button>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-table
      :columns="columns"
      :data-source="items"
      row-key="id"
      :pagination="pagination"
      @change="tableChange"
      :scroll="{ x: 'max-content' }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'level'">
          <a-tag :color="record.level === 'critical' ? 'error' : record.level === 'warning' ? 'warning' : 'blue'">
            {{ record.level }}
          </a-tag>
        </template>
        <template v-if="column.key === 'is_resolved'">
          <a-tag :color="record.is_resolved ? 'success' : 'default'">
            {{ record.is_resolved ? "已处理" : "未处理" }}
          </a-tag>
        </template>
        <template v-if="column.key === 'action'">
          <a-space>
            <a-button v-if="record.action_target" size="small" @click="goProcess(record)">
              {{ record.action_label || "去处理" }}
            </a-button>
            <a-button v-if="!record.is_resolved" size="small" type="primary" @click="resolve(record.id)">
              处理完成
            </a-button>
          </a-space>
        </template>
      </template>
    </a-table>
  </a-card>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { message } from "ant-design-vue";
import { apiFetch } from "../services/api";

const router = useRouter();
const filters = reactive({ type: "", isResolved: "", level: "", keyword: "" });
const items = ref([]);
const conflictGroups = ref([]);
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
  { title: "类型", dataIndex: "type", sorter: true, sortOrder: sortBy.value === "type" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null },
  { title: "级别", dataIndex: "level", key: "level", sorter: true, sortOrder: sortBy.value === "level" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null, width: 100 },
  { title: "标题", dataIndex: "title", ellipsis: true },
  { title: "内容", dataIndex: "content", ellipsis: true },
  { title: "状态", dataIndex: "is_resolved", key: "is_resolved", sorter: true, sortOrder: sortBy.value === "is_resolved" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null, width: 100 },
  { title: "操作", key: "action", width: 160, fixed: "right" },
]);

const conflictColumns = [
  { title: "冲突类型", dataIndex: "conflict_reason" },
  { title: "数量", dataIndex: "count", width: 80 },
  { title: "学号汇总", key: "students" },
  { title: "操作", key: "action", width: 100 },
];

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
  filters.type = "";
  filters.isResolved = "";
  filters.level = "";
  filters.keyword = "";
  page.value = 1;
  load();
}

async function copyStudents(group) {
  const text = group.joined_student_nos || "";
  if (!text) return;
  if (navigator?.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
  } else {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    document.body.removeChild(textarea);
  }
  message.success("学号已复制到剪贴板");
}

function goProcess(item) {
  if (!item.action_target) return;
  router.push(item.action_target);
}

async function loadConflictGroups() {
  const params = new URLSearchParams();
  if (filters.keyword) params.set("keyword", filters.keyword);
  if (filters.isResolved === "true") params.set("include_resolved", "true");
  const payload = await apiFetch(`/api/v1/alerts/conflict-groups${params.toString() ? `?${params.toString()}` : ""}`);
  conflictGroups.value = payload.data.items || [];
}

async function load() {
  const params = new URLSearchParams({
    page: String(page.value),
    page_size: String(pageSize.value),
    sort_by: sortBy.value,
    sort_order: sortOrder.value,
  });
  if (filters.type) params.set("type", filters.type);
  if (filters.isResolved) params.set("is_resolved", filters.isResolved);
  if (filters.level) params.set("level", filters.level);
  if (filters.keyword) params.set("keyword", filters.keyword);
  const payload = await apiFetch(`/api/v1/alerts?${params.toString()}`);
  items.value = payload.data.items;
  total.value = payload.data.total || 0;
  page.value = payload.data.page || 1;
  pageSize.value = payload.data.page_size || 20;
  await loadConflictGroups();
}

async function resolve(alertId) {
  await apiFetch(`/api/v1/alerts/${alertId}/resolve`, {
    method: "PATCH",
    body: JSON.stringify({ resolution_note: "frontend_resolved" }),
  });
  message.success("预警已处理");
  await load();
}

onMounted(load);
</script>

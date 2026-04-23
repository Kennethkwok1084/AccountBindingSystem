<template>
  <a-card :bordered="false">
    <template #title>学生台账</template>
    <template #extra>
      <a-button :loading="isStudentsLoading" @click="loadStudents">刷新</a-button>
    </template>

    <a-form layout="inline" style="margin-bottom: 16px; flex-wrap: wrap; gap: 8px;">
      <a-form-item label="学号/姓名">
        <a-input v-model:value="filters.keyword" placeholder="输入学号或姓名" allow-clear style="width: 200px;" />
      </a-form-item>
      <a-form-item label="绑定状态">
        <a-select v-model:value="filters.hasBinding" style="width: 120px;">
          <a-select-option value="">全部</a-select-option>
          <a-select-option value="true">已绑定</a-select-option>
          <a-select-option value="false">未绑定</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item>
        <a-space>
          <a-button type="primary" :loading="isStudentsLoading" @click="applyFilters">查询</a-button>
          <a-button @click="resetFilters">重置</a-button>
        </a-space>
      </a-form-item>
    </a-form>

    <a-alert v-if="pageMessage" :type="pageMessageType === 'error' ? 'error' : 'info'" :message="pageMessage" show-icon style="margin-bottom: 12px;" />

    <a-table
      :columns="columns"
      :data-source="students"
      row-key="id"
      :pagination="pagination"
      :loading="isStudentsLoading"
      @change="tableChange"
      :scroll="{ x: 'max-content' }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'action'">
          <a-button size="small" :loading="isHistoryLoading && selectedStudentNo === record.student_no" @click="selectStudent(record.student_no)">
            查看台账
          </a-button>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="detailVisible"
      :title="`学生详情 — ${detail?.student_no || ''} ${detail?.name ? '/' + detail.name : ''}`"
      :footer="null"
      :width="860"
      @cancel="closeDetails"
    >
      <template v-if="detail">
        <a-descriptions bordered size="small" :column="{ xs: 1, md: 2 }" style="margin-bottom: 16px;">
          <a-descriptions-item label="预期到期">{{ detail.expected_expire_at || "-" }}</a-descriptions-item>
          <a-descriptions-item label="来源到期">{{ detail.source_expire_at || "-" }}</a-descriptions-item>
          <a-descriptions-item label="当前绑定" :span="2">
            {{ detail.current_binding ? `${detail.current_binding.mobile_account} / ${detail.current_binding.expire_at}` : "无" }}
          </a-descriptions-item>
        </a-descriptions>

        <a-divider>绑定历史</a-divider>

        <a-space style="margin-bottom: 12px;">
          <span>动作类型：</span>
          <a-select v-model:value="historyFilters.actionType" style="width: 160px;">
            <a-select-option v-for="opt in ACTION_TYPE_OPTIONS" :key="opt.value || 'all'" :value="opt.value">
              {{ opt.label }}
            </a-select-option>
          </a-select>
          <a-button :loading="isHistoryLoading" @click="loadHistory">筛选</a-button>
        </a-space>

        <a-alert v-if="historyMessage" :type="historyMessageType === 'error' ? 'error' : 'info'" :message="historyMessage" show-icon style="margin-bottom: 12px;" />

        <a-table
          :columns="historyColumns"
          :data-source="history"
          row-key="id"
          size="small"
          :pagination="historyPagination"
          :loading="isHistoryLoading"
          @change="historyTableChange"
        />
      </template>
    </a-modal>
  </a-card>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { apiFetch } from "../services/api";
import { ACTION_TYPE_OPTIONS, getActionTypeLabel } from "../utils/ledgerActionLabels";

const filters = reactive({ keyword: "", hasBinding: "" });
const students = ref([]);
const studentsTotal = ref(0);
const studentsPage = ref(1);
const studentsPageSize = ref(20);
const sortBy = ref("student_no");
const sortOrder = ref("asc");

const selectedStudentNo = ref("");
const detail = ref(null);
const detailVisible = ref(false);
const history = ref([]);
const historyTotal = ref(0);
const historyPage = ref(1);
const historyPageSize = ref(20);
const historySortBy = ref("created_at");
const historySortOrder = ref("desc");
const historyFilters = reactive({ actionType: "" });
const isStudentsLoading = ref(false);
const isHistoryLoading = ref(false);
const pageMessage = ref("");
const pageMessageType = ref("info");
const historyMessage = ref("");
const historyMessageType = ref("info");

const pagination = computed(() => ({
  current: studentsPage.value,
  pageSize: studentsPageSize.value,
  total: studentsTotal.value,
  showTotal: (t) => `共 ${t} 条`,
  showSizeChanger: false,
}));

const historyPagination = computed(() => ({
  current: historyPage.value,
  pageSize: historyPageSize.value,
  total: historyTotal.value,
  showTotal: (t) => `共 ${t} 条`,
  showSizeChanger: false,
}));

const columns = computed(() => [
  { title: "学号", dataIndex: "student_no", sorter: true, sortOrder: sortBy.value === "student_no" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null },
  { title: "姓名", dataIndex: "name", sorter: true, sortOrder: sortBy.value === "name" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null, customRender: ({ text }) => text || "-" },
  { title: "当前账号", dataIndex: "current_mobile_account", sorter: true, sortOrder: sortBy.value === "current_mobile_account" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null, customRender: ({ text }) => text || "-" },
  { title: "绑定到期", dataIndex: "current_binding_expire_at", sorter: true, sortOrder: sortBy.value === "current_binding_expire_at" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null, customRender: ({ text }) => text || "-" },
  { title: "来源到期", dataIndex: "source_expire_at", sorter: true, sortOrder: sortBy.value === "source_expire_at" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null, customRender: ({ text }) => text || "-" },
  { title: "操作", key: "action", width: 100, fixed: "right" },
]);

const historyColumns = computed(() => [
  { title: "时间", dataIndex: "created_at", sorter: true, sortOrder: historySortBy.value === "created_at" ? (historySortOrder.value === "desc" ? "descend" : "ascend") : null },
  { title: "动作", dataIndex: "action_type", sorter: true, sortOrder: historySortBy.value === "action_type" ? (historySortOrder.value === "desc" ? "descend" : "ascend") : null, customRender: ({ text }) => getActionTypeLabel(text) },
  { title: "旧账号ID", dataIndex: "old_mobile_account_id", customRender: ({ text }) => text || "-" },
  { title: "新账号ID", dataIndex: "new_mobile_account_id", customRender: ({ text }) => text || "-" },
]);

function tableChange(pag, _filters, sorter) {
  const s = Array.isArray(sorter) ? sorter[0] : sorter;
  if (s && s.field) { sortBy.value = s.field; sortOrder.value = s.order === "descend" ? "desc" : "asc"; }
  studentsPage.value = pag.current;
  studentsPageSize.value = pag.pageSize;
  loadStudents();
}

function historyTableChange(pag, _filters, sorter) {
  const s = Array.isArray(sorter) ? sorter[0] : sorter;
  if (s && s.field) { historySortBy.value = s.field; historySortOrder.value = s.order === "descend" ? "desc" : "asc"; }
  historyPage.value = pag.current;
  historyPageSize.value = pag.pageSize;
  loadHistory();
}

function applyFilters() { studentsPage.value = 1; loadStudents(); }

function resetFilters() {
  filters.keyword = "";
  filters.hasBinding = "";
  studentsPage.value = 1;
  loadStudents();
}

function closeDetails() {
  detailVisible.value = false;
  detail.value = null;
  selectedStudentNo.value = "";
  history.value = [];
  historyFilters.actionType = "";
  historyMessage.value = "";
}

async function loadStudents() {
  pageMessage.value = "";
  isStudentsLoading.value = true;
  try {
    const params = new URLSearchParams({ page: String(studentsPage.value), page_size: String(studentsPageSize.value), sort_by: sortBy.value, sort_order: sortOrder.value });
    if (filters.keyword) params.set("keyword", filters.keyword);
    if (filters.hasBinding) params.set("has_binding", filters.hasBinding);
    const payload = await apiFetch(`/api/v1/students?${params.toString()}`);
    students.value = payload.data.items || [];
    studentsTotal.value = payload.data.total || 0;
    studentsPage.value = payload.data.page || 1;
    studentsPageSize.value = payload.data.page_size || 20;
    if (!students.value.length) { pageMessage.value = "当前筛选条件下没有学生数据"; pageMessageType.value = "info"; }
  } catch (error) {
    pageMessage.value = error.message || "学生列表加载失败";
    pageMessageType.value = "error";
  } finally {
    isStudentsLoading.value = false;
  }
}

async function selectStudent(studentNo) {
  selectedStudentNo.value = studentNo;
  historyPage.value = 1;
  historyMessage.value = "";
  const payload = await apiFetch(`/api/v1/students/${encodeURIComponent(studentNo)}`);
  detail.value = payload.data;
  detailVisible.value = true;
  await loadHistory();
}

async function loadHistory() {
  if (!selectedStudentNo.value) return;
  historyMessage.value = "";
  isHistoryLoading.value = true;
  try {
    const params = new URLSearchParams({ page: String(historyPage.value), page_size: String(historyPageSize.value), sort_by: historySortBy.value, sort_order: historySortOrder.value });
    if (historyFilters.actionType) params.set("action_type", historyFilters.actionType);
    const payload = await apiFetch(`/api/v1/students/${encodeURIComponent(selectedStudentNo.value)}/history?${params.toString()}`);
    history.value = payload.data.items || [];
    historyTotal.value = payload.data.total || 0;
    historyPage.value = payload.data.page || 1;
    historyPageSize.value = payload.data.page_size || 20;
    if (!history.value.length) { historyMessage.value = "该学生暂无历史记录"; historyMessageType.value = "info"; }
  } catch (error) {
    historyMessage.value = error.message || "学生历史加载失败";
    historyMessageType.value = "error";
  } finally {
    isHistoryLoading.value = false;
  }
}

onMounted(loadStudents);
</script>

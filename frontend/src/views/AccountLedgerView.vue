<template>
  <a-card :bordered="false">
    <template #title>账号台账</template>
    <template #extra>
      <a-space>
        <a-button :loading="exporting" @click="exportAccounts">导出 Excel</a-button>
        <a-button :loading="isAccountsLoading" @click="loadAccounts">刷新</a-button>
      </a-space>
    </template>

    <a-form layout="inline" style="margin-bottom: 16px; flex-wrap: wrap; gap: 8px;">
      <a-form-item label="账号关键字">
        <a-input v-model:value="filters.account" placeholder="输入账号" allow-clear style="width: 200px;" />
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
        <a-input v-model:value="filters.batchCode" placeholder="如 B202601" allow-clear style="width: 160px;" />
      </a-form-item>
      <a-form-item>
        <a-space>
          <a-button type="primary" :loading="isAccountsLoading" @click="applyFilters">查询</a-button>
          <a-button @click="resetFilters">重置</a-button>
        </a-space>
      </a-form-item>
    </a-form>

    <a-alert v-if="pageMessage" :type="pageMessageType === 'error' ? 'error' : 'info'" :message="pageMessage" show-icon style="margin-bottom: 12px;" />
    <a-alert v-if="exportState" type="success" message="账号台账导出已生成" show-icon style="margin-bottom: 12px;">
      <template #description>
        已生成文件 {{ exportState.filename }}，共 {{ exportState.rowCount }} 条。请前往导出记录下载。
        <div style="margin-top: 12px;">
          <a-button type="primary" size="small" @click="goToExports">前往导出记录</a-button>
        </div>
      </template>
    </a-alert>

    <a-table
      :columns="columns"
      :data-source="accounts"
      row-key="id"
      :pagination="pagination"
      :loading="isAccountsLoading"
      @change="tableChange"
      :scroll="{ x: 'max-content' }"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="STATUS_COLOR[record.status]">{{ STATUS_LABEL[record.status] || record.status }}</a-tag>
        </template>
        <template v-if="column.key === 'action'">
          <a-button size="small" :loading="isHistoryLoading && selectedAccount === record.account" @click="selectAccount(record)">
            查看台账
          </a-button>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="detailVisible"
      :title="`账号详情 — ${result?.account || ''}`"
      :footer="null"
      :width="860"
      @cancel="closeDetails"
    >
      <template v-if="result">
        <a-descriptions bordered size="small" :column="{ xs: 1, md: 2 }" style="margin-bottom: 16px;">
          <a-descriptions-item label="账号">{{ result.account }}</a-descriptions-item>
          <a-descriptions-item label="状态">
            <a-tag :color="STATUS_COLOR[result.status]">{{ STATUS_LABEL[result.status] || result.status }}</a-tag>
          </a-descriptions-item>
        </a-descriptions>

        <a-divider>使用历史</a-divider>

        <a-space style="margin-bottom: 12px;">
          <span>动作类型：</span>
          <a-select v-model:value="historyFilters.actionType" style="width: 160px;">
            <a-select-option v-for="opt in ACTION_TYPE_OPTIONS" :key="opt.value || 'all'" :value="opt.value">
              {{ opt.label }}
            </a-select-option>
          </a-select>
          <a-button :loading="isHistoryLoading" @click="loadHistory">筛选</a-button>
          <a-button :loading="historyExporting" @click="exportHistory">导出历史</a-button>
        </a-space>

        <a-alert v-if="historyMessage" :type="historyMessageType === 'error' ? 'error' : 'info'" :message="historyMessage" show-icon style="margin-bottom: 12px;" />
        <a-alert v-if="historyExportState" type="success" message="账号历史导出已生成" show-icon style="margin-bottom: 12px;">
          <template #description>
            已生成文件 {{ historyExportState.filename }}，共 {{ historyExportState.rowCount }} 条。请前往导出记录下载。
            <div style="margin-top: 12px;">
              <a-button type="primary" size="small" @click="goToHistoryExports">前往导出记录</a-button>
            </div>
          </template>
        </a-alert>

        <a-table
          :columns="historyColumns"
          :data-source="result.items || []"
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
import { useRouter } from "vue-router";
import { apiFetch } from "../services/api";
import { ACTION_TYPE_OPTIONS, getActionTypeLabel } from "../utils/ledgerActionLabels";

const router = useRouter();
const STATUS_COLOR = { available: "success", assigned: "processing", disabled: "default", expired: "warning" };
const STATUS_LABEL = { available: "可用", assigned: "已分配", disabled: "禁用", expired: "到期" };

const filters = reactive({ account: "", status: "", batchCode: "" });
const accounts = ref([]);
const accountsTotal = ref(0);
const accountsPage = ref(1);
const accountsPageSize = ref(20);
const sortBy = ref("account");
const sortOrder = ref("asc");

const selectedAccount = ref("");
const result = ref(null);
const detailVisible = ref(false);
const historyPage = ref(1);
const historyPageSize = ref(20);
const historyTotal = ref(0);
const historySortBy = ref("created_at");
const historySortOrder = ref("desc");
const historyFilters = reactive({ actionType: "" });
const isAccountsLoading = ref(false);
const isHistoryLoading = ref(false);
const pageMessage = ref("");
const pageMessageType = ref("info");
const historyMessage = ref("");
const historyMessageType = ref("info");
const exporting = ref(false);
const exportState = ref(null);
const historyExporting = ref(false);
const historyExportState = ref(null);

const pagination = computed(() => ({
  current: accountsPage.value,
  pageSize: accountsPageSize.value,
  total: accountsTotal.value,
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
  { title: "账号", dataIndex: "account", sorter: true, sortOrder: sortBy.value === "account" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null },
  { title: "状态", dataIndex: "status", key: "status", sorter: true, sortOrder: sortBy.value === "status" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null, width: 100 },
  { title: "批次", dataIndex: "batch_code", sorter: true, sortOrder: sortBy.value === "batch_code" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null },
  { title: "最近分配", dataIndex: "last_assigned_at", sorter: true, sortOrder: sortBy.value === "last_assigned_at" ? (sortOrder.value === "desc" ? "descend" : "ascend") : null, customRender: ({ text }) => text || "-" },
  { title: "操作", key: "action", width: 100, fixed: "right" },
]);

const historyColumns = computed(() => [
  { title: "时间", dataIndex: "created_at", sorter: true, sortOrder: historySortBy.value === "created_at" ? (historySortOrder.value === "desc" ? "descend" : "ascend") : null },
  { title: "动作", dataIndex: "action_type", sorter: true, sortOrder: historySortBy.value === "action_type" ? (historySortOrder.value === "desc" ? "descend" : "ascend") : null, customRender: ({ text }) => getActionTypeLabel(text) },
  { title: "学生ID", dataIndex: "student_id", sorter: true, sortOrder: historySortBy.value === "student_id" ? (historySortOrder.value === "desc" ? "descend" : "ascend") : null, customRender: ({ text }) => text || "-" },
]);

function tableChange(pag, _filters, sorter) {
  const s = Array.isArray(sorter) ? sorter[0] : sorter;
  if (s && s.field) { sortBy.value = s.field; sortOrder.value = s.order === "descend" ? "desc" : "asc"; }
  accountsPage.value = pag.current;
  accountsPageSize.value = pag.pageSize;
  loadAccounts();
}

function historyTableChange(pag, _filters, sorter) {
  const s = Array.isArray(sorter) ? sorter[0] : sorter;
  if (s && s.field) { historySortBy.value = s.field; historySortOrder.value = s.order === "descend" ? "desc" : "asc"; }
  historyPage.value = pag.current;
  historyPageSize.value = pag.pageSize;
  loadHistory();
}

function applyFilters() { accountsPage.value = 1; loadAccounts(); }

function resetFilters() {
  filters.account = "";
  filters.status = "";
  filters.batchCode = "";
  accountsPage.value = 1;
  loadAccounts();
}

function closeDetails() {
  detailVisible.value = false;
  result.value = null;
  selectedAccount.value = "";
  historyFilters.actionType = "";
  historyMessage.value = "";
  historyExportState.value = null;
}

async function loadAccounts() {
  pageMessage.value = "";
  isAccountsLoading.value = true;
  try {
    const params = new URLSearchParams({ page: String(accountsPage.value), page_size: String(accountsPageSize.value), sort_by: sortBy.value, sort_order: sortOrder.value });
    if (filters.account) params.set("account", filters.account);
    if (filters.status) params.set("status", filters.status);
    if (filters.batchCode) params.set("batch_code", filters.batchCode);
    const payload = await apiFetch(`/api/v1/mobile-accounts?${params.toString()}`);
    accounts.value = payload.data.items || [];
    accountsTotal.value = payload.data.total || 0;
    accountsPage.value = payload.data.page || 1;
    accountsPageSize.value = payload.data.page_size || 20;
    if (!accounts.value.length) { pageMessage.value = "当前筛选条件下没有账号数据"; pageMessageType.value = "info"; }
  } catch (error) {
    pageMessage.value = error.message || "账号列表加载失败";
    pageMessageType.value = "error";
  } finally {
    isAccountsLoading.value = false;
  }
}

async function selectAccount(item) {
  selectedAccount.value = item.account;
  historyPage.value = 1;
  historyMessage.value = "";
  result.value = { account: item.account, status: item.status, items: [] };
  detailVisible.value = true;
  await loadHistory();
}

async function loadHistory() {
  if (!selectedAccount.value) return;
  historyMessage.value = "";
  isHistoryLoading.value = true;
  try {
    const params = new URLSearchParams({ page: String(historyPage.value), page_size: String(historyPageSize.value), sort_by: historySortBy.value, sort_order: historySortOrder.value });
    if (historyFilters.actionType) params.set("action_type", historyFilters.actionType);
    const encodedAccount = encodeURIComponent(selectedAccount.value);
    const payload = await apiFetch(`/api/v1/ledger/accounts/${encodedAccount}?${params.toString()}`);
    result.value = payload.data;
    historyTotal.value = payload.data.total || 0;
    historyPage.value = payload.data.page || 1;
    historyPageSize.value = payload.data.page_size || 20;
    if (!payload.data.items?.length) { historyMessage.value = "该账号暂无历史记录"; historyMessageType.value = "info"; }
  } catch (error) {
    historyMessage.value = error.message || "账号历史加载失败";
    historyMessageType.value = "error";
  } finally {
    isHistoryLoading.value = false;
  }
}

async function exportHistory() {
  if (!selectedAccount.value) return;
  historyMessage.value = "";
  historyExportState.value = null;
  historyExporting.value = true;
  try {
    const encodedAccount = encodeURIComponent(selectedAccount.value);
    const payload = await apiFetch(`/api/v1/ledger/accounts/${encodedAccount}/export`, {
      method: "POST",
      body: JSON.stringify({
        action_type: historyFilters.actionType || null,
        sort_by: historySortBy.value,
        sort_order: historySortOrder.value,
      }),
    });
    historyExportState.value = {
      filename: payload.data.export_job.filename,
      rowCount: payload.data.export_job.row_count,
    };
  } catch (error) {
    historyMessage.value = error.message || "账号历史导出失败";
    historyMessageType.value = "error";
  } finally {
    historyExporting.value = false;
  }
}

async function exportAccounts() {
  pageMessage.value = "";
  exportState.value = null;
  exporting.value = true;
  try {
    const payload = await apiFetch("/api/v1/mobile-accounts/export", {
      method: "POST",
      body: JSON.stringify({
        account: filters.account,
        status: filters.status,
        batch_code: filters.batchCode,
        sort_by: sortBy.value,
        sort_order: sortOrder.value,
      }),
    });
    exportState.value = {
      filename: payload.data.export_job.filename,
      rowCount: payload.data.export_job.row_count,
    };
  } catch (error) {
    pageMessage.value = error.message || "账号台账导出失败";
    pageMessageType.value = "error";
  } finally {
    exporting.value = false;
  }
}

function goToExports() {
  router.push({ path: "/exports", query: { keyword: exportState.value?.filename || "" } });
}

function goToHistoryExports() {
  router.push({ path: "/exports", query: { keyword: historyExportState.value?.filename || "" } });
}

onMounted(loadAccounts);
</script>

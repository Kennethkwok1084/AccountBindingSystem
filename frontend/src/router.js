import { createRouter, createWebHistory } from "vue-router";
import DashboardView from "./views/DashboardView.vue";
import LoginView from "./views/LoginView.vue";
import AccountsImportView from "./views/AccountsImportView.vue";
import AccountsView from "./views/AccountsView.vue";
import BatchesView from "./views/BatchesView.vue";
import ChargeBatchView from "./views/ChargeBatchView.vue";
import ExportsView from "./views/ExportsView.vue";
import FullStudentsView from "./views/FullStudentsView.vue";
import ManualRebindView from "./views/ManualRebindView.vue";
import BatchRebindView from "./views/BatchRebindView.vue";
import AlertsView from "./views/AlertsView.vue";
import SettingsView from "./views/SettingsView.vue";
import StudentLedgerView from "./views/StudentLedgerView.vue";
import AccountLedgerView from "./views/AccountLedgerView.vue";
import AuditLogsView from "./views/AuditLogsView.vue";
import { fetchAuthMode, fetchCurrentUser } from "./services/auth";

const routes = [
  { path: "/login", component: LoginView, meta: { public: true } },
  { path: "/", redirect: "/dashboard" },
  { path: "/dashboard", component: DashboardView },
  { path: "/imports/account-pool", component: AccountsImportView },
  { path: "/accounts", component: AccountsView },
  { path: "/batches", component: BatchesView },
  { path: "/operations/charge-preview", component: ChargeBatchView },
  { path: "/imports/full-list", component: FullStudentsView },
  { path: "/operations/manual-rebind", component: ManualRebindView },
  { path: "/operations/batch-rebind", component: BatchRebindView },
  { path: "/alerts", component: AlertsView },
  { path: "/settings", component: SettingsView },
  { path: "/audit-logs", component: AuditLogsView },
  { path: "/ledger", redirect: "/ledger/students" },
  { path: "/ledger/students", component: StudentLedgerView },
  { path: "/ledger/accounts", component: AccountLedgerView },
  { path: "/exports", component: ExportsView },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to) => {
  if (to.meta.public) {
    if (to.path === "/login") {
      try {
        const mode = await fetchAuthMode();
        if (!mode.local_login_enabled) {
          await fetchCurrentUser();
          return "/dashboard";
        }
      } catch (_error) {
        return true;
      }
    }
    return true;
  }
  try {
    await fetchCurrentUser();
    return true;
  } catch (_error) {
    try {
      const mode = await fetchAuthMode();
      if (!mode.local_login_enabled) {
        return "/login";
      }
    } catch (_modeError) {
      return "/login";
    }
    return "/login";
  }
});

export default router;

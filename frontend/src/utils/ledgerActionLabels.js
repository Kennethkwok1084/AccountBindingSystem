export const ACTION_TYPE_LABELS = {
  allocate: "分配新账号",
  renew: "续费",
  rebind: "换绑",
  release: "释放绑定",
  sync_bind: "按名单绑定",
  sync_rebind: "按名单换绑",
  sync_expire_at: "同步到期时间",
  manual_fix: "手工修正",
};

export const ACTION_TYPE_OPTIONS = [
  { value: "", label: "全部动作" },
  ...Object.entries(ACTION_TYPE_LABELS).map(([value, label]) => ({ value, label })),
];

export function getActionTypeLabel(actionType) {
  return ACTION_TYPE_LABELS[actionType] || actionType || "-";
}

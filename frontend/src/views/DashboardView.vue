<template>
  <a-card :bordered="false">
    <template #title>仪表盘</template>
    <template #extra>
      <a-button @click="load">刷新</a-button>
    </template>

    <a-row :gutter="16">
      <a-col :xs="24" :sm="12" :lg="6">
        <a-card size="small" style="background: #e6f7ff; border-color: #91d5ff; border-radius: 8px;">
          <a-statistic title="可用账号" :value="state.available_accounts" :value-style="{ color: '#1890ff', fontSize: '28px' }" />
        </a-card>
      </a-col>
      <a-col :xs="24" :sm="12" :lg="6">
        <a-card size="small" style="background: #f6ffed; border-color: #b7eb8f; border-radius: 8px;">
          <a-statistic title="已分配账号" :value="state.assigned_accounts" :value-style="{ color: '#52c41a', fontSize: '28px' }" />
        </a-card>
      </a-col>
      <a-col :xs="24" :sm="12" :lg="6">
        <a-card size="small" style="background: #fff7e6; border-color: #ffd591; border-radius: 8px;">
          <a-statistic title="当前绑定" :value="state.current_bindings" :value-style="{ color: '#fa8c16', fontSize: '28px' }" />
        </a-card>
      </a-col>
      <a-col :xs="24" :sm="12" :lg="6">
        <a-card size="small" :style="{ background: state.pending_alerts > 0 ? '#fff1f0' : '#f6ffed', borderColor: state.pending_alerts > 0 ? '#ffccc7' : '#b7eb8f', borderRadius: '8px' }">
          <a-statistic
            title="未处理预警"
            :value="state.pending_alerts"
            :value-style="{ color: state.pending_alerts > 0 ? '#cf1322' : '#3f8600', fontSize: '28px' }"
          />
        </a-card>
      </a-col>
    </a-row>

    <a-row :gutter="16" style="margin-top: 24px;">
      <a-col :xs="24" :md="12">
        <a-card title="最近批次" size="small">
          <a-list :data-source="state.recent_batches" size="small" :locale="{ emptyText: '暂无数据' }">
            <template #renderItem="{ item }">
              <a-list-item>
                <a-space>
                  <a-tag>#{{ item.id }}</a-tag>
                  <span>{{ item.batch_type }}</span>
                  <a-tag :color="item.status === 'success' ? 'success' : item.status === 'failed' ? 'error' : 'default'">
                    {{ item.status }}
                  </a-tag>
                  <span>成功 {{ item.success_rows }} / 失败 {{ item.failed_rows }}</span>
                </a-space>
              </a-list-item>
            </template>
          </a-list>
        </a-card>
      </a-col>
      <a-col :xs="24" :md="12">
        <a-card title="最近导出" size="small">
          <a-list :data-source="state.recent_exports" size="small" :locale="{ emptyText: '暂无数据' }">
            <template #renderItem="{ item }">
              <a-list-item>
                <a-space>
                  <a-tag>#{{ item.id }}</a-tag>
                  <span>{{ item.filename }}</span>
                  <a-tag color="blue">{{ item.row_count }} 行</a-tag>
                </a-space>
              </a-list-item>
            </template>
          </a-list>
        </a-card>
      </a-col>
    </a-row>
  </a-card>
</template>

<script setup>
import { reactive, onMounted } from "vue";
import { apiFetch } from "../services/api";

const state = reactive({
  available_accounts: 0,
  assigned_accounts: 0,
  current_bindings: 0,
  pending_alerts: 0,
  recent_batches: [],
  recent_exports: [],
});

async function load() {
  const payload = await apiFetch("/api/v1/dashboard");
  Object.assign(state, payload.data);
}

onMounted(load);
</script>

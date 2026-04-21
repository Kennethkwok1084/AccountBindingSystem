<template>
  <section class="panel">
    <h2>仪表盘</h2>
    <button @click="load">刷新</button>
    <div class="cards">
      <article class="card">
        <strong>{{ state.available_accounts }}</strong>
        <span>可用账号</span>
      </article>
      <article class="card">
        <strong>{{ state.assigned_accounts }}</strong>
        <span>已分配账号</span>
      </article>
      <article class="card">
        <strong>{{ state.current_bindings }}</strong>
        <span>当前绑定</span>
      </article>
      <article class="card">
        <strong>{{ state.pending_alerts }}</strong>
        <span>未处理预警</span>
      </article>
    </div>
    <div class="grid-two">
      <div>
        <h3>最近批次</h3>
        <ul>
          <li v-for="item in state.recent_batches" :key="item.id">
            #{{ item.id }} {{ item.batch_type }} / {{ item.status }} / 成功 {{ item.success_rows }} / 失败 {{ item.failed_rows }}
          </li>
        </ul>
      </div>
      <div>
        <h3>最近导出</h3>
        <ul>
          <li v-for="item in state.recent_exports" :key="item.id">
            #{{ item.id }} {{ item.filename }} / {{ item.row_count }} 行
          </li>
        </ul>
      </div>
    </div>
  </section>
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


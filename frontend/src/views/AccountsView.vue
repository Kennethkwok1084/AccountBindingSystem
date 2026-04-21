<template>
  <section class="panel">
    <div class="section-heading">
      <div>
        <h2>账号池管理</h2>
        <p class="muted">按状态和批次筛选，查看详情并执行禁用或恢复。</p>
      </div>
      <button @click="load">刷新</button>
    </div>

    <form class="grid-two" @submit.prevent="load">
      <div>
        <label>状态</label>
        <select v-model="filters.status">
          <option value="">全部</option>
          <option value="available">可用</option>
          <option value="assigned">已分配</option>
          <option value="disabled">禁用</option>
          <option value="expired">到期</option>
        </select>
      </div>
      <div>
        <label>批次编码</label>
        <input v-model="filters.batchCode" placeholder="如 B202601" />
      </div>
    </form>

    <p v-if="message" class="message">{{ message }}</p>

    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>账号</th>
          <th>状态</th>
          <th>批次</th>
          <th>最近分配</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.id">
          <td>{{ item.id }}</td>
          <td>{{ item.account }}</td>
          <td>{{ item.status }}</td>
          <td>{{ item.batch_code }}</td>
          <td>{{ item.last_assigned_at || "-" }}</td>
          <td class="actions">
            <button class="link-button" @click="selectAccount(item.id)">详情</button>
            <button v-if="item.status !== 'disabled'" @click="disableAccount(item.id)">禁用</button>
            <button v-else @click="enableAccount(item.id)">恢复</button>
          </td>
        </tr>
      </tbody>
    </table>

    <div class="grid-two" v-if="selected">
      <article class="panel subpanel">
        <h3>账号详情</h3>
        <p>账号：{{ selected.account }}</p>
        <p>状态：{{ selected.status }}</p>
        <p>禁用原因：{{ selected.disabled_reason || "-" }}</p>
        <p>批次：{{ selected.batch.batch_code }} / {{ selected.batch.batch_name }}</p>
        <p>优先级：{{ selected.batch.priority }}</p>
        <p>到期日：{{ selected.batch.expire_at || "-" }}</p>
      </article>
      <article class="panel subpanel">
        <h3>账号历史</h3>
        <ul class="simple-list">
          <li v-for="item in history" :key="item.id">
            {{ item.created_at }} / {{ item.action_type }} / 学生 {{ item.student_id }}
          </li>
        </ul>
      </article>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref, onMounted } from "vue";
import { apiFetch } from "../services/api";

const filters = reactive({
  status: "",
  batchCode: "",
});
const items = ref([]);
const selected = ref(null);
const history = ref([]);
const message = ref("");

async function load() {
  const params = new URLSearchParams();
  if (filters.status) {
    params.set("status", filters.status);
  }
  if (filters.batchCode) {
    params.set("batch_code", filters.batchCode);
  }
  const payload = await apiFetch(`/api/v1/mobile-accounts${params.toString() ? `?${params.toString()}` : ""}`);
  items.value = payload.data.items;
}

async function selectAccount(accountId) {
  const [detail, historyPayload] = await Promise.all([
    apiFetch(`/api/v1/mobile-accounts/${accountId}`),
    apiFetch(`/api/v1/mobile-accounts/${accountId}/history`),
  ]);
  selected.value = detail.data;
  history.value = historyPayload.data.items;
}

async function disableAccount(accountId) {
  await apiFetch(`/api/v1/mobile-accounts/${accountId}/disable`, {
    method: "PATCH",
    body: JSON.stringify({ reason: "frontend_disable" }),
  });
  message.value = `账号 ${accountId} 已禁用`;
  await load();
}

async function enableAccount(accountId) {
  await apiFetch(`/api/v1/mobile-accounts/${accountId}/enable`, {
    method: "PATCH",
    body: JSON.stringify({}),
  });
  message.value = `账号 ${accountId} 已恢复`;
  await load();
}

onMounted(load);
</script>

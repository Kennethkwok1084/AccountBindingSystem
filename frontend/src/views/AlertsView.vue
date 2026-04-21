<template>
  <section class="panel">
    <div class="section-heading">
      <div>
        <h2>预警中心</h2>
        <p class="muted">集中处理批次到期、库存低水位和绑定冲突。</p>
      </div>
      <button @click="load">刷新</button>
    </div>

    <form class="grid-two" @submit.prevent="load">
      <div>
        <label>预警类型</label>
        <input v-model="filters.type" placeholder="如 inventory_low" />
      </div>
      <div>
        <label>处理状态</label>
        <select v-model="filters.isResolved">
          <option value="">全部</option>
          <option value="false">未处理</option>
          <option value="true">已处理</option>
        </select>
      </div>
    </form>

    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>类型</th>
          <th>级别</th>
          <th>标题</th>
          <th>内容</th>
          <th>状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.id">
          <td>{{ item.id }}</td>
          <td>{{ item.type }}</td>
          <td>{{ item.level }}</td>
          <td>{{ item.title }}</td>
          <td>{{ item.content }}</td>
          <td>{{ item.is_resolved ? "已处理" : "未处理" }}</td>
          <td>
            <button v-if="!item.is_resolved" @click="resolve(item.id)">处理完成</button>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup>
import { reactive, ref, onMounted } from "vue";
import { apiFetch } from "../services/api";

const filters = reactive({
  type: "",
  isResolved: "",
});
const items = ref([]);

async function load() {
  const params = new URLSearchParams();
  if (filters.type) {
    params.set("type", filters.type);
  }
  if (filters.isResolved) {
    params.set("is_resolved", filters.isResolved);
  }
  const payload = await apiFetch(`/api/v1/alerts${params.toString() ? `?${params.toString()}` : ""}`);
  items.value = payload.data.items;
}

async function resolve(alertId) {
  await apiFetch(`/api/v1/alerts/${alertId}/resolve`, {
    method: "PATCH",
    body: JSON.stringify({ resolution_note: "frontend_resolved" }),
  });
  await load();
}

onMounted(load);
</script>

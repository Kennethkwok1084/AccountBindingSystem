<template>
  <section class="panel">
    <h2>导出记录</h2>
    <button @click="load">刷新</button>
    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>文件名</th>
          <th>行数</th>
          <th>创建时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in exports" :key="item.id">
          <td>{{ item.id }}</td>
          <td>{{ item.filename }}</td>
          <td>{{ item.row_count }}</td>
          <td>{{ item.created_at }}</td>
          <td><a :href="`/api/v1/exports/${item.id}/download`" target="_blank">下载</a></td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { apiFetch } from "../services/api";

const exports = ref([]);

async function load() {
  const payload = await apiFetch("/api/v1/exports");
  exports.value = payload.data.items;
}

onMounted(load);
</script>


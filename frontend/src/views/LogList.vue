<template>
  <div style="margin-top: 20px">
    <div style="margin-bottom: 10px">
      <el-date-picker
        v-model="range"
        type="daterange"
        range-separator="-"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        style="margin-right: 8px"
      />
      <el-button @click="load">查询</el-button>
    </div>
    <el-table :data="logs" style="width: 100%">
      <el-table-column prop="username" label="账号" />
      <el-table-column prop="student_id" label="学号" />
      <el-table-column prop="action" label="动作" />
      <el-table-column prop="bind_time" label="时间" />
    </el-table>
    <el-pagination
      v-model:current-page="page"
      :page-size="size"
      :total="total"
      style="margin-top: 10px"
      @current-change="load"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { ElMessage } from "element-plus";
import { fetchLogs } from "../api/logs";

const logs = ref([]);
const total = ref(0);
const page = ref(1);
const size = ref(10);
const range = ref([]);

async function load() {
  try {
    const [start, end] = range.value || [];
    const params = { page: page.value, size: size.value };
    if (start) params.start = start;
    if (end) params.end = end;
    const data = await fetchLogs(params);
    logs.value = data.items;
    total.value = data.total;
  } catch {
    ElMessage.error("加载失败");
  }
}

onMounted(load);
</script>

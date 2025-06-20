<template>
  <div>
    <div style="margin-bottom: 10px">
      <el-input
        v-model="search"
        placeholder="搜索"
        style="width: 200px; margin-right: 8px"
        @change="load"
      />
      <el-select
        v-model="bound"
        placeholder="绑定状态"
        style="width: 120px; margin-right: 8px"
        @change="load"
      >
        <el-option label="全部" :value="''" />
        <el-option label="已绑定" :value="true" />
        <el-option label="未绑定" :value="false" />
      </el-select>
      <el-button @click="exportAccounts">导出</el-button>
      <el-button style="margin-left: 8px" @click="autoRelease"
        >自动释放</el-button
      >
    </div>
    <el-table :data="accounts" style="width: 100%">
      <el-table-column prop="username" label="账号" />
      <el-table-column prop="student_id" label="学号" />
      <el-table-column prop="is_bound" label="已绑定" />
      <el-table-column prop="bind_time" label="绑定时间" />
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
import {
  fetchAccounts,
  exportAccounts as exportAccApi,
  triggerAutoRelease,
} from "../api/accounts";

const accounts = ref([]);
const total = ref(0);
const page = ref(1);
const size = ref(10);
const search = ref("");
const bound = ref("");

async function load() {
  try {
    const data = await fetchAccounts({
      page: page.value,
      size: size.value,
      q: search.value,
      bound: bound.value,
    });
    accounts.value = data.items;
    total.value = data.total;
  } catch {
    ElMessage.error("加载失败");
  }
}

onMounted(load);

function exportAccounts() {
  exportAccApi();
}

async function autoRelease() {
  try {
    const { released } = await triggerAutoRelease();
    ElMessage.success(`释放 ${released} 个账号`);
    load();
  } catch {
    ElMessage.error("操作失败");
  }
}
</script>

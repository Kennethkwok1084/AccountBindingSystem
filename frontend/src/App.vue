<template>
  <div class="app" style="padding: 20px">
    <h1>CampusNet Account Management</h1>
    <el-tabs v-model="tab" style="margin-top: 10px">
      <el-tab-pane label="绑定账号" name="bind">
        <Bind />
      </el-tab-pane>
      <el-tab-pane label="导入账号" name="import">
        <Import />
      </el-tab-pane>
      <el-tab-pane label="账号列表" name="accounts">
        <AccountList />
      </el-tab-pane>
      <el-tab-pane label="日志记录" name="logs">
        <LogList />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref } from "vue";
import AccountList from "./views/AccountList.vue";
import LogList from "./views/LogList.vue";
import Bind from "./views/BindAccount.vue";
import Import from "./views/ImportAccounts.vue";

const tab = ref("bind");
</script>

<style></style>

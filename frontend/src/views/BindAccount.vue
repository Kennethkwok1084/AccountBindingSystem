<template>
  <div style="margin-top: 20px">
    <el-form :model="form" label-width="80px" style="max-width: 300px">
      <el-form-item label="账号">
        <el-input v-model="form.username" />
      </el-form-item>
      <el-form-item label="学号">
        <el-input v-model="form.student_id" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="submit">绑定</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { reactive } from "vue";
import { ElMessage } from "element-plus";
import { bindAccount } from "../api/accounts";

const form = reactive({ username: "", student_id: "" });

async function submit() {
  try {
    await bindAccount(form);
    ElMessage.success("绑定成功");
    form.username = "";
    form.student_id = "";
  } catch {
    ElMessage.error("绑定失败");
  }
}
</script>

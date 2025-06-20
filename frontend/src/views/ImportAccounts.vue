<template>
  <div style="margin-top: 20px">
    <el-upload
      :auto-upload="false"
      accept=".xlsx"
      v-model:file-list="files"
      action=""
      style="margin-bottom: 10px"
    />
    <el-button type="primary" @click="upload">上传</el-button>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { ElMessage } from "element-plus";
import { importAccounts } from "../api/accounts";

const files = ref([]);

async function upload() {
  if (files.value.length === 0) {
    ElMessage.error("请选择文件");
    return;
  }
  try {
    const [file] = files.value;
    const imported = await importAccounts(file.raw);
    ElMessage.success(`成功导入 ${imported} 条`);
    files.value = [];
  } catch {
    ElMessage.error("上传失败");
  }
}
</script>

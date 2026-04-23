<template>
  <a-card :bordered="false">
    <template #title>批次到期批量换号</template>

    <a-alert
      type="info"
      message="用于处理某个批次到期后，该批次下所有已绑定学生统一换到其他可用账号。流程：先预览影响范围，再人工确认执行。若无可用新账号，对应学生会在结果中显示失败原因。"
      style="margin-bottom: 20px;"
    />

    <a-space style="margin-bottom: 16px;">
      <a-input-number
        v-model:value="batchId"
        placeholder="输入批次 ID"
        :min="1"
        style="width: 180px;"
      />
      <a-button type="primary" @click="preview" :disabled="!batchId">预览</a-button>
    </a-space>

    <template v-if="previewData">
      <a-descriptions bordered size="small" style="margin-bottom: 16px;">
        <a-descriptions-item label="批次编码">{{ previewData.batch_code }}</a-descriptions-item>
        <a-descriptions-item label="影响人数">{{ previewData.items.length }} 人</a-descriptions-item>
        <a-descriptions-item label="可执行">
          <a-tag color="success">{{ executableCount }} 人</a-tag>
        </a-descriptions-item>
        <a-descriptions-item label="缺少账号">
          <a-tag :color="previewData.items.length - executableCount > 0 ? 'warning' : 'default'">
            {{ previewData.items.length - executableCount }} 人
          </a-tag>
        </a-descriptions-item>
      </a-descriptions>

      <a-button type="primary" @click="execute" style="margin-bottom: 16px;">确认执行批量换号</a-button>

      <a-table
        :columns="columns"
        :data-source="previewData.items"
        :row-key="r => `${r.student_no}-${r.old_account}`"
        size="small"
        :pagination="{ pageSize: 20, showTotal: t => `共 ${t} 条` }"
      />
    </template>
  </a-card>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { message } from "ant-design-vue";
import { apiFetch, createIdempotencyKey } from "../services/api";

const route = useRoute();
const batchId = ref(null);
const previewData = ref(null);

const executableCount = computed(() => {
  const items = previewData.value?.items || [];
  return items.filter((item) => item.can_execute).length;
});

const columns = [
  { title: "学号", dataIndex: "student_no" },
  { title: "姓名", dataIndex: "name" },
  { title: "旧账号", dataIndex: "old_account" },
  { title: "新账号", dataIndex: "new_account", customRender: ({ text }) => text || "-" },
  { title: "状态", dataIndex: "message" },
];

async function preview() {
  const payload = await apiFetch("/api/v1/batch-rebinds/preview", {
    method: "POST",
    body: JSON.stringify({ batch_id: Number(batchId.value) }),
  });
  previewData.value = payload.data;
}

async function execute() {
  const payload = await apiFetch(`/api/v1/batch-rebinds/${Number(batchId.value)}/execute`, {
    method: "POST",
    headers: { "X-Idempotency-Key": createIdempotencyKey("batch-rebind") },
    body: JSON.stringify({ confirm: true }),
  });
  message.success(`执行完成：成功 ${payload.data.success_rows}，失败 ${payload.data.failed_rows}`);
}

onMounted(() => {
  if (route.query.batch_id) {
    batchId.value = Number(route.query.batch_id);
    preview();
  }
});
</script>

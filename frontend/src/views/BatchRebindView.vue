<template>
  <section class="panel">
    <h2>批次换绑</h2>
    <form class="inline-form" @submit.prevent="preview">
      <label>批次 ID</label>
      <input v-model="batchId" type="number" />
      <button type="submit">预览</button>
    </form>
    <div v-if="previewData">
      <p>批次 {{ previewData.batch_code }}</p>
      <button @click="execute">执行批次换绑</button>
      <ul>
        <li v-for="item in previewData.items" :key="`${item.student_no}-${item.old_account}`">
          {{ item.student_no }} / {{ item.old_account }} -> {{ item.new_account || "无" }} / {{ item.message }}
        </li>
      </ul>
    </div>
  </section>
</template>

<script setup>
import { ref } from "vue";
import { apiFetch, createIdempotencyKey } from "../services/api";

const batchId = ref("");
const previewData = ref(null);

async function preview() {
  const payload = await apiFetch("/api/v1/batch-rebinds/preview", {
    method: "POST",
    body: JSON.stringify({ batch_id: Number(batchId.value) }),
  });
  previewData.value = payload.data;
}

async function execute() {
  await apiFetch(`/api/v1/batch-rebinds/${Number(batchId.value)}/execute`, {
    method: "POST",
    headers: {
      "X-Idempotency-Key": createIdempotencyKey("batch-rebind"),
    },
    body: JSON.stringify({ confirm: true }),
  });
}
</script>

<template>
  <section class="panel">
    <div class="section-heading">
      <div>
        <h2>系统设置</h2>
        <p class="muted">统一维护套餐天数、水位、库存阈值和完整名单工作表。</p>
      </div>
      <button @click="load">刷新</button>
    </div>

    <form @submit.prevent="save">
      <div class="grid-two">
        <div v-for="item in configEntries" :key="item.key">
          <label>{{ item.label }}</label>
          <input v-model="form[item.key]" />
          <p class="muted">{{ item.remark }}</p>
        </div>
      </div>
      <button type="submit">保存设置</button>
    </form>

    <p v-if="message" class="message">{{ message }}</p>
  </section>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from "vue";
import { apiFetch } from "../services/api";

const form = reactive({});
const metadata = ref({});
const message = ref("");

const configEntries = computed(() =>
  Object.entries(metadata.value).map(([key, value]) => ({
    key,
    label: key,
    remark: value.remark || "",
  })),
);

async function load() {
  const payload = await apiFetch("/api/v1/config");
  metadata.value = payload.data;
  Object.entries(payload.data).forEach(([key, value]) => {
    form[key] = value.value;
  });
}

async function save() {
  await apiFetch("/api/v1/config", {
    method: "PUT",
    body: JSON.stringify(form),
  });
  message.value = "系统设置已更新";
  await load();
}

onMounted(load);
</script>

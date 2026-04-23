<template>
  <a-card :bordered="false">
    <template #title>系统设置</template>
    <template #extra>
      <a-button @click="load">刷新</a-button>
    </template>

    <a-alert
      type="info"
      message="统一维护套餐天数、水位、库存阈值和完整名单工作表。"
      style="margin-bottom: 20px;"
    />

    <a-form layout="vertical" @finish="save">
      <a-row :gutter="24">
        <a-col :xs="24" :md="12" v-for="item in configEntries" :key="item.key">
          <a-form-item :label="item.label">
            <a-input v-model:value="form[item.key]" />
            <div style="font-size: 12px; color: #8c8c8c; margin-top: 4px;">{{ item.remark }}</div>
          </a-form-item>
        </a-col>
      </a-row>
      <a-form-item>
        <a-button type="primary" html-type="submit">保存设置</a-button>
      </a-form-item>
    </a-form>
  </a-card>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from "vue";
import { message } from "ant-design-vue";
import { apiFetch } from "../services/api";

const form = reactive({});
const metadata = ref({});

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
  message.success("系统设置已更新");
  await load();
}

onMounted(load);
</script>

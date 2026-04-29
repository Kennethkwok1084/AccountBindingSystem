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

    <a-alert v-if="testResult" :type="testResult.type" :message="testResult.message" show-icon style="margin-bottom: 20px;">
      <template #description v-if="testResult.description">
        {{ testResult.description }}
      </template>
    </a-alert>

    <a-form layout="vertical" @submit.prevent>
      <a-card
        v-for="group in groupedEntries"
        :key="group.group"
        :title="group.group"
        size="small"
        style="margin-bottom: 16px;"
      >
        <a-row :gutter="24">
          <a-col :xs="24" :md="12" v-for="item in group.items" :key="item.key">
            <a-form-item :label="item.label">
              <a-switch v-if="item.type === 'boolean'" v-model:checked="form[item.key]" />
              <a-input-number v-else-if="item.type === 'number'" v-model:value="form[item.key]" style="width: 100%;" />
              <a-select v-else-if="item.type === 'select'" v-model:value="form[item.key]" style="width: 100%;">
                <a-select-option v-for="opt in item.options" :key="opt.value" :value="opt.value">{{ opt.label }}</a-select-option>
              </a-select>
              <a-input v-else v-model:value="form[item.key]" />
              <div style="font-size: 12px; color: #8c8c8c; margin-top: 4px;">{{ item.remark }}</div>
              <div style="font-size: 12px; color: #bfbfbf; margin-top: 2px;">配置键：{{ item.key }}</div>
            </a-form-item>
          </a-col>
        </a-row>
      </a-card>
      <a-form-item>
        <a-space>
          <a-button type="primary" :loading="saving" @click="save">保存设置</a-button>
          <a-button :loading="testingSyslog" @click="testSyslog">测试 Syslog 连通性</a-button>
        </a-space>
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
const saving = ref(false);
const testingSyslog = ref(false);
const testResult = ref(null);

const configEntries = computed(() =>
  Object.entries(metadata.value).map(([key, value]) => ({
    key,
    label: value.label || key,
    remark: value.remark || "",
    type: value.type || "text",
    group: value.group || "其他",
    options: value.options || [],
  })),
);

const groupedEntries = computed(() => {
  const groups = new Map();
  for (const item of configEntries.value) {
    if (!groups.has(item.group)) {
      groups.set(item.group, []);
    }
    groups.get(item.group).push(item);
  }
  return Array.from(groups.entries()).map(([group, items]) => ({ group, items }));
});

async function load() {
  const payload = await apiFetch("/api/v1/config");
  metadata.value = payload.data;
  Object.entries(payload.data).forEach(([key, value]) => {
    form[key] = value.value;
  });
}

async function save() {
  saving.value = true;
  try {
    await apiFetch("/api/v1/config", {
      method: "PUT",
      body: JSON.stringify(form),
    });
    message.success("系统设置已更新");
    await load();
  } catch (error) {
    message.error(error.message || "系统设置保存失败");
  } finally {
    saving.value = false;
  }
}

async function testSyslog() {
  testingSyslog.value = true;
  testResult.value = null;
  try {
    const payload = await apiFetch("/api/v1/config/test-syslog", {
      method: "POST",
      body: JSON.stringify(form),
    });
    testResult.value = {
      type: "success",
      message: payload.data.message,
      description: `目标 ${payload.data.host}:${payload.data.port}，协议 ${String(payload.data.protocol).toUpperCase()}，应用名 ${payload.data.app_name}`,
    };
  } catch (error) {
    testResult.value = {
      type: "error",
      message: error.message || "Syslog 连通性测试失败",
      description: "",
    };
  } finally {
    testingSyslog.value = false;
  }
}

onMounted(load);
</script>

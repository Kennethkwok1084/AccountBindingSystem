<template>
  <section class="panel">
    <div class="section-heading">
      <div>
        <h2>批次管理</h2>
        <p class="muted">支持新建批次、调整优先级、到期日和预警天数。</p>
      </div>
      <button @click="load">刷新</button>
    </div>

    <div class="grid-two">
      <article class="panel subpanel">
        <h3>新建批次</h3>
        <form @submit.prevent="createBatch">
          <label>批次编码</label>
          <input v-model="createForm.batch_code" />
          <label>批次名称</label>
          <input v-model="createForm.batch_name" />
          <label>类型</label>
          <input v-model="createForm.batch_type" placeholder="normal/free/recycle/special" />
          <label>优先级</label>
          <input v-model="createForm.priority" type="number" />
          <label>预警天数</label>
          <input v-model="createForm.warn_days" type="number" />
          <label>到期日</label>
          <input v-model="createForm.expire_at" type="date" />
          <label>备注</label>
          <textarea v-model="createForm.remark"></textarea>
          <button type="submit">创建批次</button>
        </form>
      </article>

      <article class="panel subpanel" v-if="editForm.id">
        <h3>编辑批次</h3>
        <form @submit.prevent="updateBatch">
          <label>批次编码</label>
          <input :value="editForm.batch_code" disabled />
          <label>批次名称</label>
          <input v-model="editForm.batch_name" />
          <label>类型</label>
          <input v-model="editForm.batch_type" />
          <label>优先级</label>
          <input v-model="editForm.priority" type="number" />
          <label>预警天数</label>
          <input v-model="editForm.warn_days" type="number" />
          <label>到期日</label>
          <input v-model="editForm.expire_at" type="date" />
          <label>状态</label>
          <select v-model="editForm.status">
            <option value="active">active</option>
            <option value="inactive">inactive</option>
          </select>
          <label>备注</label>
          <textarea v-model="editForm.remark"></textarea>
          <button type="submit">保存批次</button>
        </form>
      </article>
    </div>

    <p v-if="message" class="message">{{ message }}</p>

    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>编码</th>
          <th>名称</th>
          <th>类型</th>
          <th>优先级</th>
          <th>预警天数</th>
          <th>到期日</th>
          <th>状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.id">
          <td>{{ item.id }}</td>
          <td>{{ item.batch_code }}</td>
          <td>{{ item.batch_name }}</td>
          <td>{{ item.batch_type }}</td>
          <td>{{ item.priority }}</td>
          <td>{{ item.warn_days }}</td>
          <td>{{ item.expire_at || "-" }}</td>
          <td>{{ item.status }}</td>
          <td><button class="link-button" @click="startEdit(item)">编辑</button></td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup>
import { reactive, ref, onMounted } from "vue";
import { apiFetch } from "../services/api";

const items = ref([]);
const message = ref("");
const createForm = reactive({
  batch_code: "",
  batch_name: "",
  batch_type: "normal",
  priority: 100,
  warn_days: 1,
  expire_at: "",
  remark: "",
});
const editForm = reactive({
  id: null,
  batch_code: "",
  batch_name: "",
  batch_type: "",
  priority: 100,
  warn_days: 1,
  expire_at: "",
  status: "active",
  remark: "",
});

async function load() {
  const payload = await apiFetch("/api/v1/batches");
  items.value = payload.data.items;
}

async function createBatch() {
  await apiFetch("/api/v1/batches", {
    method: "POST",
    body: JSON.stringify(createForm),
  });
  message.value = `批次 ${createForm.batch_code} 已创建`;
  Object.assign(createForm, {
    batch_code: "",
    batch_name: "",
    batch_type: "normal",
    priority: 100,
    warn_days: 1,
    expire_at: "",
    remark: "",
  });
  await load();
}

function startEdit(item) {
  Object.assign(editForm, item);
}

async function updateBatch() {
  await apiFetch(`/api/v1/batches/${editForm.id}`, {
    method: "PUT",
    body: JSON.stringify(editForm),
  });
  message.value = `批次 ${editForm.batch_code} 已更新`;
  await load();
}

onMounted(load);
</script>

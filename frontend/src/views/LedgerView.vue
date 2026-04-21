<template>
  <section class="panel">
    <h2>台账查询</h2>
    <div class="grid-two">
      <form @submit.prevent="searchStudent">
        <label>按学号查</label>
        <input v-model="studentNo" />
        <button type="submit">查询学生</button>
      </form>
      <form @submit.prevent="searchAccount">
        <label>按账号查</label>
        <input v-model="account" />
        <button type="submit">查询账号</button>
      </form>
    </div>
    <pre v-if="studentResult">{{ studentResult }}</pre>
    <pre v-if="accountResult">{{ accountResult }}</pre>
  </section>
</template>

<script setup>
import { ref } from "vue";
import { apiFetch } from "../services/api";

const studentNo = ref("");
const account = ref("");
const studentResult = ref("");
const accountResult = ref("");

async function searchStudent() {
  const detail = await apiFetch(`/api/v1/students/${studentNo.value}`);
  const history = await apiFetch(`/api/v1/students/${studentNo.value}/history`);
  studentResult.value = JSON.stringify({ detail: detail.data, history: history.data.items }, null, 2);
}

async function searchAccount() {
  const payload = await apiFetch(`/api/v1/ledger/accounts/${account.value}`);
  accountResult.value = JSON.stringify(payload.data, null, 2);
}
</script>


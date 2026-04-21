<template>
  <section class="panel">
    <h2>账号台账</h2>
    <form class="inline-form" @submit.prevent="search">
      <input v-model="account" placeholder="输入移动账号" />
      <button type="submit">查询</button>
    </form>

    <article class="panel subpanel" v-if="result">
      <h3>账号详情</h3>
      <p>账号：{{ result.account }}</p>
      <p>状态：{{ result.status }}</p>
      <ul class="simple-list">
        <li v-for="item in result.items" :key="item.id">
          {{ item.created_at }} / {{ item.action_type }} / 学生 {{ item.student_id }}
        </li>
      </ul>
    </article>
  </section>
</template>

<script setup>
import { ref } from "vue";
import { apiFetch } from "../services/api";

const account = ref("");
const result = ref(null);

async function search() {
  const payload = await apiFetch(`/api/v1/ledger/accounts/${account.value}`);
  result.value = payload.data;
}
</script>

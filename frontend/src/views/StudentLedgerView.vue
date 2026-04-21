<template>
  <section class="panel">
    <h2>学生台账</h2>
    <form class="inline-form" @submit.prevent="search">
      <input v-model="studentNo" placeholder="输入学号" />
      <button type="submit">查询</button>
    </form>

    <article class="panel subpanel" v-if="detail">
      <h3>学生详情</h3>
      <p>学号：{{ detail.student_no }}</p>
      <p>姓名：{{ detail.name }}</p>
      <p>预期到期：{{ detail.expected_expire_at || "-" }}</p>
      <p>来源到期：{{ detail.source_expire_at || "-" }}</p>
      <p>
        当前绑定：
        {{ detail.current_binding ? `${detail.current_binding.mobile_account} / ${detail.current_binding.expire_at}` : "无" }}
      </p>
    </article>

    <article class="panel subpanel" v-if="history.length">
      <h3>绑定历史</h3>
      <ul class="simple-list">
        <li v-for="item in history" :key="item.id">
          {{ item.created_at }} / {{ item.action_type }} / {{ item.old_mobile_account_id || "-" }} -> {{ item.new_mobile_account_id || "-" }}
        </li>
      </ul>
    </article>
  </section>
</template>

<script setup>
import { ref } from "vue";
import { apiFetch } from "../services/api";

const studentNo = ref("");
const detail = ref(null);
const history = ref([]);

async function search() {
  const [detailPayload, historyPayload] = await Promise.all([
    apiFetch(`/api/v1/students/${studentNo.value}`),
    apiFetch(`/api/v1/students/${studentNo.value}/history`),
  ]);
  detail.value = detailPayload.data;
  history.value = historyPayload.data.items;
}
</script>

<script setup lang="ts">
import { ref } from 'vue'
import SimpleSwarm from './SimpleSwarm.vue'
import SwarmShell from './SwarmShell.vue'

const advanced = ref(localStorage.getItem('daswarm-ui-mode') === 'advanced')

function showAdvanced() {
  advanced.value = true
  localStorage.setItem('daswarm-ui-mode','advanced')
}
function showSimple() {
  advanced.value = false
  localStorage.setItem('daswarm-ui-mode','simple')
}
</script>

<template>
  <div>
    <SimpleSwarm v-if="!advanced" @advanced="showAdvanced" />
    <div v-else class="advanced-wrap">
      <button class="simple-return" @click="showSimple">← Simple view</button>
      <SwarmShell />
    </div>
  </div>
</template>

<style scoped>
.advanced-wrap{position:relative}.simple-return{position:fixed;right:18px;bottom:18px;z-index:200;background:#143746;border:1px solid #4a8da5;color:#d9f6ff;border-radius:999px;padding:9px 14px;font:12px Inter,Segoe UI,Arial,sans-serif;box-shadow:0 8px 28px #0008;cursor:pointer}.simple-return:hover{background:#1a4a5f}
</style>

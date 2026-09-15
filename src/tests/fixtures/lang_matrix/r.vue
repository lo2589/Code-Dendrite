<template>
  <button id="app" @click="main()">{{ label }}</button>
</template>
<script>
function helper() { return 1 }
function main() { return helper() }
export default { name: 'demo', methods: { main } }
</script>

<script>
function helper() { return 1 }
function main() { return helper() }
</script>
<button id="app" on:click={main}>{label}</button>

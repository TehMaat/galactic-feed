<script>
  let { name, label = "" } = $props();
</script>

<svg class="ico" aria-hidden={label ? undefined : "true"} role={label ? "img" : undefined} aria-label={label || undefined}><use href="#i-{name}" /></svg>

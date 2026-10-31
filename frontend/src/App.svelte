<script>
  import { onMount } from "svelte";
  import Shell from "./Shell.svelte";
  import { boot, session } from "./lib/store.svelte.js";
  import Auth from "./views/Auth.svelte";

  onMount(boot);
</script>

{#if session.phase === "loading"}
  <div class="boot" aria-busy="true"><svg class="ico" aria-hidden="true"><use href="#i-orbit" /></svg></div>
{:else if session.phase === "ready"}
  <Shell />
{:else}
  <Auth />
{/if}

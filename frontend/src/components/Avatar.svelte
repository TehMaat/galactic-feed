<script>
  // Avatar del profilo (#76): la foto, se c'è, oppure le iniziali su uno dei colori proposti.
  import { AVATAR_COLORS } from "../lib/format.js";

  let { user, size = "md", photo = undefined, color = undefined, name = undefined } = $props();
  const src = $derived(photo !== undefined ? photo : user?.avatar);
  const hue = $derived(AVATAR_COLORS[(color ?? user?.avatar_color ?? 0) % AVATAR_COLORS.length]);
  const letters = $derived(
    (name ?? user?.display_name ?? user?.username ?? "?")
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .map((w) => w[0] || "")
      .join("")
      .toUpperCase() || "?",
  );
</script>

{#if src}
  <img class="avatar {size}" {src} alt="" decoding="async" />
{:else}
  <span class="avatar {size}" style="--av-a:{hue[0]};--av-b:{hue[1]}" aria-hidden="true">{letters}</span>
{/if}

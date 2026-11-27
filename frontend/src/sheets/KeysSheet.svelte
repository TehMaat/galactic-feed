<script>
  // Elenco delle scorciatoie da tastiera (#94), aperto con «?».
  import Sheet from "../components/Sheet.svelte";
  import { SHORTCUTS } from "../lib/keys.js";
</script>

<Sheet name="keys" title="Scorciatoie da tastiera">
  <div class="keys-sheet">
    <div class="set-group">
      {#each SHORTCUTS as [key, label] (key)}
        <div class="set-row"><span>{label}</span><kbd class="kbd">{key}</kbd></div>
      {/each}
    </div>
    <p class="set-note">Funzionano quando non stai scrivendo in un campo. «Salva», «Segna» e «Apri l'originale» valgono per l'articolo aperto.</p>
  </div>
</Sheet>

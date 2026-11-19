<script>
  // Nome e avatar del profilo (#76): una foto (ridotta qui a 256 px prima di mandarla) oppure le
  // iniziali su un colore. Il nome utente per entrare non cambia.
  import { untrack } from "svelte";
  import Avatar from "../components/Avatar.svelte";
  import Icon from "../components/Icon.svelte";
  import Sheet from "../components/Sheet.svelte";
  import { AVATAR_COLORS } from "../lib/format.js";
  import { closeSheet, saveProfile, session, setAvatar, toast, ui } from "../lib/store.svelte.js";

  let name = $state("");
  let color = $state(0);
  let photo = $state(null); // data: URL nuova, "" per togliere la foto, null se non cambia
  let busy = $state(false);

  // Solo all'apertura: salvando il nome session.user cambia, e non deve riportare indietro la foto scelta.
  $effect(() => {
    if (ui.sheet === "profile") {
      untrack(() => {
        const u = session.user;
        name = u.display_name || "";
        color = u.avatar_color || 0;
        photo = null;
      });
    }
  });

  const shown = $derived(photo === null ? session.user?.avatar : photo || null);

  function pick(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const img = new Image();
    img.onload = () => {
      const size = 256;
      const canvas = document.createElement("canvas");
      canvas.width = canvas.height = size;
      const side = Math.min(img.width, img.height);
      canvas.getContext("2d").drawImage(img, (img.width - side) / 2, (img.height - side) / 2, side, side, 0, 0, size, size);
      photo = canvas.toDataURL("image/jpeg", 0.85);
      URL.revokeObjectURL(img.src);
    };
    img.onerror = () => toast("Questa foto non si apre: prova con un JPEG o un PNG.");
    img.src = URL.createObjectURL(file);
  }

  async function save(e) {
    e.preventDefault();
    busy = true;
    const newPhoto = photo;
    let ok = await saveProfile({ display_name: name, avatar_color: color });
    if (ok && newPhoto !== null) ok = await setAvatar(newPhoto || null);
    busy = false;
    if (ok) {
      toast("Profilo aggiornato");
      closeSheet();
    }
  }
</script>

<Sheet name="profile" title="Il tuo profilo">
  <form class="form-stack profile-edit" onsubmit={save}>
    <div class="pe-head">
      <Avatar user={session.user} size="xl" photo={shown} {color} {name} />
      <div class="pe-actions">
        <label class="btn-secondary small"><Icon name="camera" />{shown ? "Cambia foto" : "Carica una foto"}
          <input type="file" accept="image/jpeg,image/png,image/webp" onchange={pick} />
        </label>
        {#if shown}<button type="button" class="btn-secondary small" onclick={() => (photo = "")}>Usa le iniziali</button>{/if}
      </div>
      {#if !shown}
        <div class="av-colors" role="radiogroup" aria-label="Colore delle iniziali">
          {#each AVATAR_COLORS as [a, b], i}
            <button type="button" role="radio" aria-checked={color === i} aria-label="Colore {i + 1}" style="--av-a:{a};--av-b:{b}" onclick={() => (color = i)}></button>
          {/each}
        </div>
      {/if}
    </div>
    <div class="field">
      <label for="pe-name">Nome</label>
      <input class="input" id="pe-name" type="text" maxlength="60" autocomplete="name" bind:value={name} />
      <p class="hint">Si vede nel Profilo e in Amministrazione. Per entrare resta @{session.user?.username}.</p>
    </div>
    <div class="row-actions">
      <button type="button" class="btn-secondary" onclick={closeSheet}>Annulla</button>
      <button type="submit" class="btn-primary" disabled={busy}>{busy ? "Salvo…" : "Salva"}</button>
    </div>
  </form>
</Sheet>

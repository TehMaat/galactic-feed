// Filtri del Notiziario (#68): le voci che si possono includere o escludere e il riepilogo a parole.
// Le chiavi sono le stesse del server (reading/query.py): t:<tag>, g:<gruppo>, f:<cartella>|f:none,
// s:<fonte>, c:<nazione>, v (video).
import { countryName, flag, folderColor } from "./format.js";

/** Le sezioni del pannello Filtri, con le voci: { key, label, color?, icon? }. */
export function filterGroups(data) {
  const interests = [
    ...data.tags.map((t) => ({ key: `t:${t.id}`, label: t.name, color: folderColor(t.color) })),
    ...(data.interests.groups || []).filter((g) => g.mode === "interest").map((g) => ({ key: `g:${g.id}`, label: g.name, icon: "spark" })),
  ];
  const folders = [
    ...data.folders.map((f) => ({ key: `f:${f.id}`, label: f.name, color: folderColor(f.color) })),
    ...(data.sources.some((s) => s.folder_id == null) && data.folders.length ? [{ key: "f:none", label: "Senza cartella", color: folderColor("grigio") }] : []),
  ];
  const countries = [...new Set(data.sources.map((s) => s.country).filter(Boolean))].sort();
  return [
    { id: "interessi", title: "Interessi", items: interests },
    { id: "tipo", title: "Tipo", items: [{ key: "v", label: "Video", icon: "play" }] },
    { id: "cartelle", title: "Cartelle", items: folders },
    { id: "nazioni", title: "Nazioni", items: countries.length > 1 ? countries.map((c) => ({ key: `c:${c}`, label: `${flag(c)} ${countryName(c)}` })) : [] },
    { id: "fonti", title: "Fonti", items: data.sources.map((s) => ({ key: `s:${s.id}`, label: s.title, source: s })) },
  ].filter((g) => g.items.length);
}

/** Il nome leggibile di una chiave, per il riepilogo. */
export function keyLabel(key, data) {
  for (const group of filterGroups(data)) {
    const item = group.items.find((i) => i.key === key);
    if (item) return item.label;
  }
  return key === "v" ? "Video" : "una voce non più disponibile";
}

/** «Tutte · non letti · solo Spazio, Tecnologia · senza Motori». */
export function describeFilter(f, data) {
  const parts = [f.scope === "perte" ? "Per te" : "Tutte"];
  if (f.unread) parts.push("non letti");
  if (f.inc.length) parts.push("solo " + f.inc.map((k) => keyLabel(k, data)).join(", "));
  if (f.exc.length) parts.push("senza " + f.exc.map((k) => keyLabel(k, data)).join(", "));
  return parts.join(" · ");
}

/** «12 notizie · 5 da leggere», «1 notizia · tutte lette» (#66). */
export function tallyText(t) {
  if (!t) return "";
  const n = t.total === 1 ? "1 notizia" : `${t.total} notizie`;
  return t.unread ? `${n} · ${t.unread} da leggere` : t.total ? `${n} · ${t.total === 1 ? "letta" : "tutte lette"}` : "Nessuna notizia";
}

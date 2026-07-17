# 02 — Research: concorrenza sull'istanza multimodale condivisa

## Parent Spec

[vlm-llamacpp-multimodal-wayfinder.md](../../specs/vlm-llamacpp-multimodal-wayfinder.md)

## Type

research

## Outcome

Capire come si comporta **un'unica istanza `llama-server` multimodale** quando
serve contemporaneamente le **reazioni testo** (loop Reactor, provider
`llamacpp`) e il **captioning** (pompa di percezione video): impatto della
serializzazione con `--parallel 1`, e se `--parallel 2` è sostenibile in VRAM
su 4 GB. Raccomandazione sul valore di `--parallel` e sui ritmi
(`video_fps`, cadenze) compatibili.

## Acceptance Criteria

- [ ] Misura della latenza di una reazione testo mentre una caption è in corso
      (e viceversa) con `--parallel 1`: di quanto si allunga la coda.
- [ ] VRAM dell'istanza multimodale con `--parallel 2` vs `--parallel 1` su
      4 GB: ci sta senza OOM? di quanto cresce la KV cache?
- [ ] Stima del tasso reale di richieste: `video_fps` (default 1.0) × dedup, e
      cadenza reazioni; verificare se la contention è un problema reale ai
      ritmi di default o solo in picchi.
- [ ] Raccomandazione: `--parallel 1` (serializza, accettabile) vs `--parallel 2`
      (concorrenza, se la VRAM regge), con i numeri a supporto.
- [ ] Numeri e raccomandazione ripiegati nel map.

## Blocked By

- None — indagabile in parallelo al ticket 01 (stessa istanza multimodale).

## Frontier

Determina se "istanza unica" è praticabile senza degradare né reazioni né
caption; alimenta la decisione 03 e lo spike 04.

## Work Plan

1. Avviare l'istanza multimodale (come ticket 01) con `--parallel 1`.
2. Script throwaway: lanciare in concorrenza una richiesta testo lunga e una
   di captioning; misurare le latenze osservate lato client.
3. Rilanciare con `--parallel 2`; misurare VRAM (`nvidia-smi`) e latenze.
4. Incrociare con i ritmi reali (leggere `video_fps`/cadenze da config ed
   esempi) per stimare la frequenza di collisione.
5. Scrivere la raccomandazione nel ticket e nel map.

## Evidence to Capture

- Latenze osservate con e senza contention, per parallel 1 e 2.
- `nvidia-smi` per parallel 1 vs 2.
- Frequenza stimata di richieste concorrenti ai ritmi di default.

## Out of Scope

- Qualità delle caption (ticket 01).
- Implementazione (ticket 05).

---

## Risultati (2026-07-16)

Unica istanza multimodale (E2B + mmproj) su :8090, GPU libera. Misurate una
reazione testo (~40 tok) e una caption (frame 960×540) da sole e in concorrenza
(due thread) sullo stesso server, con `--parallel 1` e `--parallel 2`.

### Latenza

| Scenario | solo testo | solo caption | concorrenti (testo / caption / wall) |
|----------|-----------|--------------|--------------------------------------|
| `--parallel 1` | 0.68 s | 0.45 s | 0.30 s / 0.74 s / **0.74 s** |
| `--parallel 2` | 0.66 s | 0.68 s | 0.29 s / 0.54 s / **0.54 s** |

Con `--parallel 1` le due richieste si accodano ma, essendo entrambe
sub-secondo, la wall combinata resta ~0.74 s. Con `--parallel 2` girano
davvero in parallelo (wall ~ max delle due).

### VRAM

| | VRAM istanza |
|---|---|
| `--parallel 1` | 2601 MiB / 4094 |
| `--parallel 2` | 2611 MiB / 4094 |

La KV cache a `-c 4096` divisa su 2 slot costa **+10 MiB**: `--parallel 2` sta
comodamente nei 4 GB.

### Frequenza reale di collisione

`video_fps` di default = 1.0 (con dedup dei frame quasi-identici, spesso meno);
le reazioni sono guidate dalla cadenza del Reactor (secondi). Le richieste
concorrenti sono quindi rare e comunque sub-secondo: la contesa **non è un
problema reale ai ritmi di default**.

### Raccomandazione

**`--parallel 2`**: vera concorrenza testo+visione a costo VRAM trascurabile
(+10 MiB), elimina anche il raro accodamento nei picchi. `--parallel 1` resta
accettabile (sub-secondo comunque). Va nella doc operatore / comando di avvio
del ticket 05.

### Criteri di accettazione

- [x] Latenza reazione durante caption in corso (e viceversa) con `--parallel 1`.
- [x] VRAM `--parallel 2` vs `1` su 4 GB: +10 MiB, nessun OOM.
- [x] Stima del tasso reale di richieste (video_fps 1.0 + dedup, cadenza reattore).
- [x] Raccomandazione (`--parallel 2`) con numeri a supporto.
- [x] Numeri e raccomandazione ripiegati nel map.

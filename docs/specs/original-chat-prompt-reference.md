# Riferimento: prompt original-chat di enkk (trascrizione dagli screenshot)

## Type

Reference (artefatto del ticket 01 di
[original-chat-prompt-fidelity-wayfinder](./original-chat-prompt-fidelity-wayfinder.md))

## Status

Parziale — trascritto dai 4 screenshot forniti il 2026-07-17. Gli screenshot sono
a risoluzione media: la **struttura, gli header e il testo delle regole** sono
leggibili con buona confidenza; alcuni **contenuti d'esempio dinamici**
(riassunto, nomi utente, singole righe di chat) sono parzialmente illeggibili e
comunque **NON vanno copiati** come testo runtime (regola del PRD padre).

> Legenda confidenza: 🟢 alta · 🟡 media (verificare) · 🔴 illeggibile/incompleto.
> Marcatura contenuto: **[STRUTTURA]** = da replicare · **[ESEMPIO]** = contenuto
> dinamico, non copiare.

---

## Layout complessivo (ordine sezioni)

Dall'alto in basso, nel prompt di reazione original-chat:

1. `[REGOLE]` + `[MEMORIA PERMANENTE]` (prefisso stabile — già nel codice) 🟡
2. `====== SITUAZIONE ATTUALE ======` + `Ti trovi nel canale di enkk.` 🟢
3. `[MEMORIA]` (riassunto rolling: STREAM / CONVERSAZIONI CON LO STREAMER / CONVERSAZIONI IN CHAT) 🟢
4. `[CHAT RECENTE]` (+ eventuali `[PARLATO RECENTE]` / `[SCHERMO RECENTE]`) 🟢/🟡
5. `[I TUOI ULTIMI MESSAGGI]` 🟢
6. `[FORMATO RISPOSTA]` 🟢
7. `[SITUAZIONE]` (varia per trigger) 🟢

> Nota: la posizione esatta del prefisso stabile `[REGOLE]`/`[MEMORIA PERMANENTE]`
> rispetto a `====== SITUAZIONE ATTUALE ======` non è interamente visibile negli
> screenshot (🔴). Da confermare col ticket 05.

---

## Sezione: apertura SITUAZIONE ATTUALE — img 2 🟢

**[STRUTTURA]**
```
====== SITUAZIONE ATTUALE ======
Ti trovi nel canale di enkk.
```
> Nel codice questa apertura è **assente**. Ticket 05. Il canale ("enkk") va preso
> dalla config, non hard-coded, se configurabile.

---

## Sezione: [MEMORIA] (riassunto rolling) — img 2 🟢 struttura / 🔴 contenuto

**[STRUTTURA]**
```
[MEMORIA] (com'e' andata la live e le conversazioni recenti)
STREAM: <paragrafo riassunto stream>
CONVERSAZIONI CON LO STREAMER:
- <bullet per scambio con lo streamer>
CONVERSAZIONI IN CHAT: minnarone ha parlato con: <utente> (<tema>), <utente> (<tema>), ...
```
**[ESEMPIO]** (NON copiare — contenuto dinamico, parzialmente leggibile 🔴): il
riassunto stream su "video di Marcolino / sala cinema / Trump / churner", la lista
utenti (marc3lly99K, fabricius_faber, buffer_overflow7, ocraM7ad, LoScarlone,
samuele_ciampini, obs_ninja, gianni1425, principerosso, eSCAVatore_, vabenetutto0,
gianghet, giangy11...). Serve solo a capire la FORMA, non è testo da inserire.

> Questa sezione è l'output del Summarizer (ticket 06). Confronto col codice: oggi
> il summary va sotto `[RIASSUNTO]` come testo libero piatto, non sotto `[MEMORIA]`
> con le tre sotto-sezioni.

---

## Sezione: prompt del Summarizer / "sintetizzatore" — img 2 (riquadro rosso) 🟢 struttura

**[STRUTTURA]**
```
Sei un sintetizzatore. Mantieni un riassunto breve in italiano di come sta
evolvendo la live: cosa fa e dice lo streamer, di cosa parla la chat, l'atmosfera.
Integra i nuovi eventi, tieni cio' che e' ancora rilevante e scarta il vecchio.
Solo il riassunto, niente preamboli.

Riassunto attuale:
<riassunto precedente reiniettato>

Eventi recenti:
STREAMER ha detto:
- <riga>
SCHERMO:
- <riga>
CHAT:
- <utente>: <riga>   (oppure "<utente> <riga>")

Aggiorna il riassunto.
```
**[ESEMPIO]** (NON copiare): "allora ragazzi adesso provo a sistemare il dedup dei
messaggi" (STREAMER), "Un editor di codice con una funzione python evidenziata"
(SCHERMO), "finalmente funziona KEKW" (CHAT).

> Confronto col codice (`summarizer.py:34-69`): oggi è
> `"Riassumi in modo conciso cosa è successo finora... ## EVENTI"` con lista piatta
> e SENZA reiniettare il riassunto precedente. Divergenza A (ticket 06).
> ⚠️ Wording esatto del blocco rosso da riverificare a piena risoluzione (🟡): il
> testo dell'istruzione è leggibile ma non garantito parola-per-parola.

---

## Sezione: [CHAT RECENTE] — formato riga — img 2 🟢 formato / 🔴 contenuto

**[STRUTTURA]** — formato riga percezione:
```
[CHAT RECENTE] (stile, tono ed emote usati ora in chat)
-23s <leo95nf>: KEKW
-<N>s <utente>: <testo>
```
Elementi del formato: prefisso `-<N>s` (secondi fa), username tra `< >`, poi
`: <testo>`. 🟢

> Confronto col codice (`perception.py:127`): oggi `format_perception_line` rende
> `leo95nf: KEKW` — **niente `-Ns`, niente `< >`**. Divergenza B (ticket 03).
> Etichetta esatta della sezione (`(stile, tono ed emote...)`) 🟡 da riverificare.

---

## Sezione: [I TUOI ULTIMI MESSAGGI] — formato riga — img 3 🟢

**[STRUTTURA]**
```
[I TUOI ULTIMI MESSAGGI] (per non ripeterti)
-277s tu: "<messaggio>" (rispondevi a: <breve reason>)
```
Elementi: prefisso `-<N>s`, `tu:`, messaggio tra virgolette doppie, suffisso
`(rispondevi a: <reason>)`. 🟢

**[ESEMPIO]** (NON copiare): `"@pandemonium_mp ma io non apro canali, mi tengo la
sub qui" (rispondevi a: risposta a proposta sub)`, `"@ogva no, la tengo per enkk
e non la regalo"`, `"OMEGALUL" (rispondevi a: accodamento alla chat)`.

> Confronto col codice (`prompt.py:546-558`): header `[TUOI MESSAGGI RECENTI]`,
> righe `minnarone: <msg>`. Divergenza C (ticket 04). Etichetta `(per non
> ripeterti)` 🟡 da riverificare.

---

## Sezione: [FORMATO RISPOSTA] — img 3 🟢 (GIÀ COINCIDENTE)

```
[FORMATO RISPOSTA]
Rispondi in ESATTAMENTE due righe:
RE: <a cosa stai rispondendo, 3-6 parole>
MSG: <il messaggio di chat> oppure #end_conv
```
> Byte-identico al codice (`prompt.py:222-226`). Non toccare.

---

## Sezione: [SITUAZIONE] — varianti trigger — img 3

### Idle 🟢 (GIÀ COINCIDENTE)
```
Nessuno ti ha interpellato. Se ti va, butta li' un commento breve e naturale su
cosa sta succedendo ora (la voce dello streamer, lo schermo o la chat). Niente di
forzato: se non hai nulla di buono da dire, MSG: #end_conv.
```
> Byte-identico al codice (`prompt.py:425-429`).

### Streamer → TE 🟡
```
Lo streamer si e' rivolto a TE (ti ha nominato o sta riprendendo un tuo
messaggio). Rispondigli, in modo naturale e tenendo il filo di cio' che vi siete
detti ([ULTIMI MESSAGGI] e [MEMORIA]).
```
> Il codice (`prompt.py:466-471`) chiude con "...vi siete detti." SENZA il
> riferimento `([ULTIMI MESSAGGI] e [MEMORIA])`. Divergenza D (ticket 02).
> ⚠️ La chiusura tra parentesi è parzialmente coperta nello screenshot (🟡):
> confermare se è `([ULTIMI MESSAGGI] e [MEMORIA])` o `[I TUOI ULTIMI MESSAGGI]`.

### Streamer continuation 🟢
```
Lo streamer ha parlato poco dopo un tuo messaggio: POTREBBE star continuando lo
scambio con te, ma non e' detto. Guarda il suo parlato recente e [I TUOI ULTIMI
MESSAGGI] per capire se ti sta davvero rispondendo: RIFLETTICI ATTENTAMENTE. Se
si', fornisci un nuovo messaggio coerente; se no, rispondi con MSG: #end_conv.
```
> Il codice cita `[CONVERSAZIONE RECENTE]` invece di `[I TUOI ULTIMI MESSAGGI]`
> (`prompt.py:459-461`). Divergenza D (ticket 02).

### Chat mention 🟢 (frase-core già coincidente)
```
<utente> ti ha scritto in chat: "<messaggio>". Rispondigli (di solito inizia con
@<utente>). Puoi tenere botta con la chat, ma con leggerezza, senza accanirti su
una persona sola. Se non c'e' nulla da rispondere, MSG: #end_conv.
```
> ⚠️ Nell'originale il messaggio è **inline** nella frase (`...ti ha scritto in
> chat: "ciao enkk, cosa usi..."`). Nel codice (`prompt.py:448-454`) la frase-core
> coincide, ma il messaggio percepito è reso **sotto, dentro il fence**. Poiché il
> fence è TENUTO (decisione 2026-07-17), questa resta una micro-differenza
> accettata: NON si mette il testo percepito inline fuori dal fence.

---

## Immagini 1 e 4 — TUI (non-prompt)

Gli screenshot 1 e 4 mostrano la **dashboard TUI** (finestre CHAT / EVENTI /
MINNARONE / TRASCRIZIONE / VIDEO), non testo di prompt. L'img 4 conferma le fonti
percettive audio (`[ALTRO]`/`[STREAMER]` con orari) e video (caption in inglese),
ma non aggiunge testo di prompt da trascrivere.

---

## Verifica anti-injection (fence)

Negli screenshot **non è visibile alcun fence** attorno al testo percepito:
conferma che il fence `DATI_PERCEPITI` è un'aggiunta di questo repo. Decisione
2026-07-17: **si tiene**. È l'unica differenza deliberata dall'originale.

---

## Incognite residue (da chiudere con screenshot a piena risoluzione)

- 🔴 Posizione del prefisso stabile `[REGOLE]`/`[MEMORIA PERMANENTE]` rispetto a
  `SITUAZIONE ATTUALE`.
- 🟡 Wording esatto, parola-per-parola, del prompt del sintetizzatore (riquadro
  rosso img 2).
- 🟡 Etichette parentetiche delle sezioni: `[CHAT RECENTE] (stile, tono ed emote…)`
  e `[I TUOI ULTIMI MESSAGGI] (per non ripeterti)`.
- 🟡 Chiusura esatta della variante "Streamer → TE" (`[ULTIMI MESSAGGI]` vs
  `[I TUOI ULTIMI MESSAGGI]`).
- 🟡 Se `[PARLATO RECENTE]`/`[SCHERMO RECENTE]` esistono come sezioni separate
  nell'originale o se lì c'è solo `[CHAT RECENTE]`.
- 🟡 Formato riga della CHAT dentro l'input del Summarizer (`<utente>: testo` vs
  `<utente> testo`) e se porta timestamp.

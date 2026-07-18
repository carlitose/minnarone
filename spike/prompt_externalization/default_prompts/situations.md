<!--
Set "a chiavi": 6 varianti di _original_chat_situation (source × kind).
Ogni sezione `## <chiave>` è il testo di prosa della situazione. Il FENCE dei
dati percepiti NON è qui: resta cablato in prompt.py (sicurezza). I riferimenti
di sezione ([CONVERSAZIONE RECENTE], [I TUOI ULTIMI MESSAGGI], [MEMORIA]) e il
token #end_conv DEVONO sopravvivere: la validazione li controlla.
-->

## idle
Nessuno ti ha interpellato. Se ti va, butta li' un commento breve e naturale su cosa sta succedendo ora (la voce dello streamer, lo schermo o la chat). Niente di forzato: se non hai nulla di buono da dire, MSG: #end_conv.

## chat_mention
{{user}} ti ha scritto in chat. Rispondigli (di solito inizia con {{mention}}). Puoi tenere botta con la chat, ma con leggerezza, senza accanirti su una persona sola. Se non c'e' nulla da rispondere, MSG: #end_conv.

## chat_continuation
{{user}} ha scritto in chat poco dopo un tuo messaggio: POTREBBE star continuando lo scambio con te, ma non e' detto. Guarda [CONVERSAZIONE RECENTE] per capire se ti sta davvero rispondendo: RIFLETTICI ATTENTAMENTE. Se si', rispondigli (di solito inizia con {{mention}}); se no, MSG: #end_conv.

## audio_mention
Lo streamer si e' rivolto a TE (ti ha nominato o sta riprendendo un tuo messaggio). Rispondigli, in modo naturale e tenendo il filo di cio' che vi siete detti ([I TUOI ULTIMI MESSAGGI] e [MEMORIA]).

## audio_continuation
Lo streamer ha parlato poco dopo un tuo messaggio: POTREBBE star continuando lo scambio con te, ma non e' detto. Guarda il suo parlato recente e [I TUOI ULTIMI MESSAGGI] per capire se ti sta davvero rispondendo: RIFLETTICI ATTENTAMENTE. Se si', fornisci un nuovo messaggio coerente; se no, rispondi con MSG: #end_conv.

## fallback
Reagisci a questa percezione ({{reason}}):

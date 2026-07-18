<!--
Keyed set: 6 variants of the reaction situation (source × kind). Each
`## <key>` section is the prose of the situation. The perceived-data FENCE is
NOT here: it stays hard-coded in prompt.py (safety). Section references and the
#end_conv token MUST survive: validation checks them.
-->

## idle
Nobody has addressed you. If you feel like it, drop a short, natural comment about what is happening right now (the streamer's voice, the screen or the chat). Nothing forced: if you have nothing good to say, MSG: #end_conv.

## chat_mention
{{user}} wrote to you in chat. Reply to them (usually starting with {{mention}}). You can banter with chat, but lightly, without piling on a single person. If there is nothing to reply, MSG: #end_conv.

## chat_continuation
{{user}} wrote in chat shortly after a message of yours: they MIGHT be continuing the exchange with you, but not necessarily. Look at [CONVERSAZIONE RECENTE] to tell whether they are really replying to you: THINK CAREFULLY. If yes, reply (usually starting with {{mention}}); if not, MSG: #end_conv.

## audio_mention
The streamer addressed YOU (mentioned you or picked up a message of yours). Reply naturally, keeping the thread of what you said to each other ([I TUOI ULTIMI MESSAGGI] and [MEMORIA]).

## audio_continuation
The streamer spoke shortly after a message of yours: they MIGHT be continuing the exchange with you, but not necessarily. Look at their recent speech and [I TUOI ULTIMI MESSAGGI] to tell whether they are really replying to you: THINK CAREFULLY. If yes, provide a new coherent message; if not, reply with MSG: #end_conv.

## fallback
React to this perception ({{reason}}):

## Parent PRD

[os-capture-teams-commentator.md](../../prds/os-capture-teams-commentator.md)

## What to build

La dataclass frozen `OsCaptureConfig` con la sua validazione a mano e il suo
`from_dict`, testata **in isolamento** (non ancora integrata in `Config`, che è
lo slice 04). Modella la sezione `os_capture:` del file YAML. Vedi *Implementation
Decisions → OsCaptureConfig* nel PRD per i campi e i default.

Campi e default: `audio: bool = True`, `video: bool = True`,
`audio_chunk_seconds: float = 1.0`, `video_fps: float = 1.0`, `monitor: int = 1`.
Regola: almeno uno fra `audio`/`video` deve essere abilitato.

## Step-by-step implementation plan

1. Definire `OsCaptureConfig` sul modello di `TwitchConfig`: dataclass frozen con
   `__post_init__` che valida tipi e valori (booleani per `audio`/`video`;
   `audio_chunk_seconds`/`video_fps` numerici > 0; `monitor` intero >= 1; almeno
   un canale abilitato) sollevando `ConfigError` con messaggi puntuali. *Perché
   ora:* è indipendente dall'hardware e da `Config`, quindi mergeabile e testabile
   da solo.
2. Aggiungere `from_dict` che rifiuta i **campi sconosciuti** (come fa
   `TwitchConfig.from_dict`) e applica i default.
3. Riusare, dove possibile, le utility di validazione già esistenti per fps e
   dimensione dei chunk PCM, così i vincoli restano coerenti col path Twitch.
4. Unit test: default corretti; ogni regola di validazione fallisce con
   `ConfigError`; campo sconosciuto rifiutato; `audio: false, video: false`
   rifiutato. *Verifica:* test verdi, `make quality` pulito.

Trappole: non ignorare silenziosamente campi sconosciuti; non accettare `bool`
dove serve un numero (bug classico: `True` è `int`); mantenere i messaggi di
errore nello stile `os_capture.<campo>: ...`.

## Acceptance criteria

- [ ] Esiste `OsCaptureConfig` con i campi/default del PRD.
- [ ] `from_dict` rifiuta campi sconosciuti e valori invalidi con `ConfigError`.
- [ ] La regola "almeno audio o video" è validata.
- [ ] Unit test coprono default e ogni ramo di validazione.

## Blocked by

None - can start immediately

## User stories addressed

- User story 5
- User story 6

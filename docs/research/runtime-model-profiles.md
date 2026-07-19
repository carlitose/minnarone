# Profili runtime e acquisizione modelli

## Domanda di ricerca

Come può un nuovo operatore scegliere un profilo Minnarone ripetibile, dal solo
Twitch chat al runtime multimodale completo, senza dipendere da pesi o path già
presenti sulla macchina dell'autore?

## Risposta e decisione

Il progetto deve pubblicare sei profili progressivi: **chat-only**, **capture
smoke**, **CPU-light audio**, **Apple Silicon full**, **CUDA full** e
**llama.cpp full**. “Full” include chat, Streamlink, audio, Whisper, speaker
embedding, video e VLM; non significa che ogni backend debba risiedere insieme
in VRAM.

Il setup resta esplicito: docs e un piccolo manifest versionato descrivono
source, licenza, revision, dimensione e SHA-256; la futura skill
`minnarone-runtime-doctor` del ticket 16 verifica tool, spazio, file e config.
Non viene introdotto uno script che scarica implicitamente molti GB e
`minnarone --check` non viene descritto come una prova dei modelli: oggi diversi
backend sono lazy e si inizializzano solo al primo evento.

Le soglie hardware sotto sono **planning envelope**, non benchmark o garanzie.
L'unico profilo full misurato in modo completo è CUDA; Apple Silicon e CPU
richiedono ancora smoke da clone pulito.

## Inventario delle dipendenze

| Canale/capacità | Extra `uv` | Tool di sistema | Modello |
| --- | --- | --- | --- |
| Twitch chat cloud | base | nessuno oltre Python 3.11+ e `uv` | nessun modello locale; un provider llama.cpp eredita invece tutti i prerequisiti P5 |
| Raw audio/video smoke Twitch | base per il comando smoke | Streamlink CLI + FFmpeg | nessuno |
| ASR isolato | `asr` | FFmpeg/Streamlink solo per catturare lo stream | faster-whisper snapshot |
| Audio completo | `audio` | Streamlink + FFmpeg per Twitch | faster-whisper + speaker ONNX |
| Video Twitch + VLM torch | `video`, `vlm` | Streamlink + FFmpeg | Qwen2-VL-compatible snapshot |
| Screen capture + VLM torch | `os-capture`, `vlm` | permessi OS di cattura | Qwen2-VL-compatible snapshot |
| VLM su llama.cpp | `video`, `vlm-llamacpp` per Twitch; `os-capture`, `vlm-llamacpp` per desktop | `llama-server`; Streamlink + FFmpeg per Twitch | GGUF + `mmproj` compatibili |
| Dashboard | `tui` | terminale compatibile | nessuno |

Gli import sono lazy, ma non tutti i check lo sono allo stesso modo:
`speaker_embedding.model_path` deve esistere quando viene costruito il runtime;
Qwen carica al primo frame; `llama-server` viene verificato via `/health` e, per
la visione, `/props`. `uv.lock` è il pin delle dipendenze Python; non pinna i
pesi.

## Matrice dei profili supportati

| Profilo | Canali e installazione | Budget minimo / raccomandato | Verifica di accettazione |
| --- | --- | --- | --- |
| **P0 chat-only** | `uv sync`; Twitch `chat: true`, audio/video false; provider cloud OpenRouter | min: 2 core, 2 GB RAM, 1 GB disco; rec: 4 core, 4 GB RAM. Nessuna GPU o peso locale | `minnarone <config> --check`, poi chat smoke bounded; shadow non richiede token send |
| **P1 capture smoke** | base; Streamlink CLI + FFmpeg; raw chat/audio/video senza ASR/VLM | min: 2 core, 4 GB RAM, 2 GB disco libero; rec: 4 core, 8 GB. Nessuna GPU | smoke separati chat, `--no-chat --audio`, `--no-chat --video`, poi combinato; controllare `stats.json` per canale |
| **P2 CPU-light audio** | `uv sync --extra audio`; chat+audio, video/VLM false; ASR pinned + CAM++ English | min: 4 core, 8 GB RAM, 4 GB disco; rec: 8 core, 16 GB RAM, 6 GB disco. `int8`, CPU | embedding 512/norma circa 1, ASR PCM plausibile, poi shadow audio; nessun path assoluto |
| **P3 Apple Silicon full** | `audio`, `video`, `vlm`, `tui`; Qwen2-VL-2B non quantizzato; `device: mps`, `device_map: null`; ASR prima su CPU int8 | min provvisorio: M1/M2, 16 GB unified RAM, 12 GB disco; rec: 32 GB unified RAM, 20 GB disco. Nessun minimo misurato | smokes isolati, caption singolo, poi 0.2–1 fps in shadow; monitorare RAM/queue e ridurre fps prima del modello |
| **P4 CUDA full** | `audio`, `video`, `vlm`, `tui`; Qwen2-VL-2B NF4 4-bit; ASR CPU per lasciare VRAM al VLM | GPU validata: NVIDIA 4 GB VRAM; planning envelope: 16 GB RAM/12 GB disco min, 8+ GB VRAM/32 GB RAM/20 GB disco rec | run di riferimento: ~1.5 GB VRAM VLM, ~3.5 s/caption warm; smokes isolati e shadow full prima del live |
| **P5 llama.cpp full/local** | `audio`, `video`, `vlm-llamacpp`, `tui`; percorso canonico Gemma GGUF+mmproj già misurato; Qwen2-VL GGUF è variante sperimentale pinned | GPU validata sul bundle Gemma: 4 GB VRAM; planning envelope: 16 GB RAM/8 GB disco min, 8 GB VRAM/32 GB RAM/12 GB disco rec. CPU-only ammesso ma non misurato | `/health`, `/props` con visione, `--check`, caption singolo e shadow; `--parallel 2` richiede contesto totale sufficiente |

P0/P1 sono i profili pubblici di ingresso. P2 abilita tutto l'audio richiesto
senza il costo del VLM. P3–P5 soddisfano il percorso “voglio audio, video,
Streamlink, Whisper e VLM”, ma restano progressive: ogni componente deve passare
lo smoke isolato prima della composizione.

## Manifest dei modelli raccomandati

I digest identificano gli artifact upstream correnti consultati il 2026-07-18;
non provano che i vecchi run locali usassero gli stessi byte. Il manifest da
prototipare nel ticket 16 deve conservare tutti questi campi.

| Uso | Owner/artifact | Licenza e pin | Dimensione / SHA-256 |
| --- | --- | --- | --- |
| ASR italiano | `dropbox-dash/faster-whisper-large-v3-turbo`, `model.bin` | MIT; revision `0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf` | 1,617,884,929 B; `e76620f83d5f5b69efd3d87e3dc180c1bd21df9fbebacfd4335e5e1efcc018da` |
| Speaker italiano/non-Mandarin | k2-fsa asset `3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx`; owner modello 3D-Speaker | Apache-2.0; release sherpa-onnx `speaker-recongition-models`; famiglia upstream English VoxCeleb v1.0.2 | 29,596,978 B; `357a834f702b80161e5b981182c038e18553c1f2ca752ed6cec2052365d4129b` |
| VLM torch | `Qwen/Qwen2-VL-2B-Instruct` | Apache-2.0; revision `895c3a49bc3fa70a340399125c650a463535e71c` | shard 1: 3,988,609,112 B / `994ac2b03f97de8bc647d0fe5eba2e4b632b3e28dc03574c29bdfc36cf47e1b9`; shard 2: 429,441,656 B / `92540d8353c8d226a589a3b179bdb33851c970ee2cc2ac7ba035f79425e7b833` |
| LLM+VLM llama.cpp | `unsloth/gemma-4-E2B-it-qat-GGUF`: `gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf` + `mmproj-F16.gguf` | Apache-2.0; revision `66a399f68ddd113b06dff02fca9523e55465d11d` | GGUF 2,620,370,976 B / `e531007218dfab990486a5de7676a6932d6ea8dea233d1f698d7c21cf8a16889`; mmproj 985,654,080 B / `13c8966d1635d02e6727f27402880614906fa291850c07feda18dbcddf2291b6` |
| Qwen VLM llama.cpp | `ggml-org/Qwen2-VL-2B-Instruct-GGUF`: `Qwen2-VL-2B-Instruct-Q4_K_M.gguf` + `mmproj-Qwen2-VL-2B-Instruct-Q8_0.gguf` | Apache-2.0; revision `bb307c036e8a1ed7b663bbd0c35b41c4c9294cfd` | GGUF 986,046,944 B / `5745685d2e607a82a0696c1118e56a2a1ae0901da450fd9cd4f161c6b62867d7`; mmproj 709,883,360 B / `a0ad91f00a7a80dcf84d719a61b00ee2e07b71794f4ee2dfa81a254621a8c418` |
| llama.cpp runtime | `ggml-org/llama.cpp` | MIT; release `b10016`, commit `32b741c336decea914e4c1c24a9c9815485901b2` | `llama-b10016-bin-win-cuda-13.3-x64.zip`, 145,700,678 B: `2c367deffa72f0ccd6881aedcfd09e12c66f2f00113bbbed4158fcd3064f662d` |

Per Hugging Face, scaricare una snapshot alla revision esatta in una directory
locale invece di usare un alias mobile. Verificare ogni file con SHA-256 prima
del primo run. Per llama.cpp, usare l'asset ufficiale della stessa release sulla
propria piattaforma oppure compilare il commit indicato; il digest in tabella
non si applica ad altre piattaforme.

Gemma è il bundle llama.cpp canonico perché già misurato nel repository;
Qwen2-VL GGUF è una variante sperimentale pinned per mantenere la stessa
famiglia del backend torch, ma non ha ancora uno smoke hardware locale
registrato. Entrambi richiedono un `mmproj` della stessa revision del GGUF.

## Risoluzione del rischio speaker `zh-cn`

Il precedente CAM++ Mandarin
`3dspeaker_speech_campplus_sv_zh-cn_16k-common.onnx` è 192-dim (upstream v1.0.0,
28,281,138 B, SHA-256
`f682b514c05d947ee3fa91cd6ec6c5c7543479a128373fa29b1faedccd21fd11`).
Ha provato l'integrazione, ma sull'italiano ha depresso la similarità e causato
over-segmentation. Non è più la raccomandazione pubblica.

Per italiano e altri stream non-Mandarin il profilo supportato usa English
VoxCeleb CAM++ 512-dim e:

```yaml
speaker_embedding:
  model_path: .local/models/speaker/3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx
  provider: cpu
  num_threads: 2
  dimension: 512

speaker_clustering:
  threshold: 0.5
```

La scelta ha evidenza HITL interna: 45 battute in un run italiano, 11
`streamer`, 27 `altro`, 7 `?`, marking manuale funzionante. È evidenza di
accettazione su un canale, non una garanzia universale; la soglia va osservata
e ritoccata per dominio/rumore.

## Layout e acquisizione portabili

Usare un layout gitignored relativo alla root di lavoro:

```text
.local/models/
  asr/large-v3-turbo/<revision>/
  speaker/3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx
  qwen2-vl-2b/<revision>/
  llamacpp/b10016/
  gguf/gemma-4-e2b/<revision>/
```

Nessun esempio pubblico deve contenere `/Users/...`, `C:\Users\...` o un path
dell'autore. Attenzione: oggi solo `soul_path`, `facts_dir` e `prompts_dir`
sono risolti rispetto alla config; i path modello relativi dipendono dal cwd.
Il doctor deve mostrare il path risolto e il tutorial deve eseguire i comandi
dalla root del progetto finché questo contratto non cambia.

Per ogni acquisizione:

1. creare la directory destinazione;
2. scaricare dall'owner alla revision/tag indicata, mai da mirror anonimi;
3. produrre un file manifest con URL, revision, filename, byte e SHA-256;
4. verificare il digest (`sha256sum` oppure `shasum -a 256`);
5. puntare la config alla snapshot locale e lanciare prima lo smoke isolato.

## Superficie di setup scelta

| Opzione | Esito |
| --- | --- |
| Solo docs | Necessarie come fonte leggibile, ma insufficienti: non rilevano file sbagliati, spazio o mismatch 192/512. |
| Script download | Non scelto ora: policy proxy/licenze/piattaforme e pesi multi-GB rendono pericoloso un download implicito. |
| `minnarone doctor` core | Utile in futuro, ma troppo presto per allargare la CLI stabile prima del prototipo 16. |
| Skill `minnarone-runtime-doctor` + manifest | **Scelta da prototipare nel 16**: guida l'acquisizione esplicita, calcola digest, verifica tool/config/hardware e rimanda ai docs; non avvia né promuove live. |

Il risultato minimo del doctor è una matrice PASS/FAIL/SKIP per Python, extra,
Streamlink, FFmpeg, spazio, modello/revision/digest, dimension speaker,
llama-server, config `--check` e smoke scelto. Non deve scaricare o cancellare
pesi senza conferma separata.

## Comandi eseguibili per profilo

Sostituire `examplechannel` e i file config locali; esportare prima le
credenziali richieste. I comandi assumono il layout `.local/models` sopra e
artifact già acquisiti e verificati.

P0 chat-only:

```bash
uv sync
uv run minnarone .local/examplechannel/chat.yaml --check
uv run minnarone-twitch-chat-smoke \
  --channel examplechannel --duration 30 \
  --output .smoke/p0-chat
```

P1 capture smoke, senza modelli:

```bash
streamlink --version
ffmpeg -version
uv run minnarone-twitch-smoke \
  --channel examplechannel --duration 30 --no-chat --audio \
  --quality audio_only --output .smoke/p1-audio
uv run minnarone-twitch-smoke \
  --channel examplechannel --duration 30 --no-chat --video \
  --video-fps 0.2 --quality 720p --output .smoke/p1-video
```

P2 CPU-light audio; i due smoke usano il PCM prodotto da P1:

```bash
uv sync --extra audio --extra tui
shasum -a 256 \
  .local/models/speaker/3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx
uv run minnarone .local/examplechannel/cpu-audio.yaml --check
uv run --extra audio python - <<'PY'
from pathlib import Path
from minnarone.asr import AsrConfig, FasterWhisperAsr
from minnarone.audio import SpeechSegment

pcm = Path(".smoke/p1-audio/raw/audio/audio-0001.pcm").read_bytes()
segment = SpeechSegment(samples=pcm, sample_rate=16_000, source_label="smoke", ts=0)
asr = FasterWhisperAsr(AsrConfig(
    model=".local/models/asr/large-v3-turbo/0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf",
    device="cpu", compute_type="int8", language="it",
))
print(asr.transcribe(segment))
PY
uv run --extra audio python - <<'PY'
from pathlib import Path
from minnarone.audio import SpeechSegment
from minnarone.speaker import SherpaOnnxSpeakerEmbeddingBackend, SpeakerEmbeddingConfig

pcm = Path(".smoke/p1-audio/raw/audio/audio-0001.pcm").read_bytes()
segment = SpeechSegment(samples=pcm, sample_rate=16_000, source_label="smoke", ts=0)
backend = SherpaOnnxSpeakerEmbeddingBackend(SpeakerEmbeddingConfig(
    model_path=".local/models/speaker/3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx",
    provider="cpu", num_threads=2, dimension=512,
))
embedding = backend.embed(segment)
print({"dimension": len(embedding), "norm": sum(x*x for x in embedding) ** 0.5})
PY
```

P3 Apple Silicon full; il caption smoke usa il JPEG prodotto da P1:

```bash
system_profiler SPHardwareDataType
uv sync --extra audio --extra video --extra vlm --extra tui
uv run minnarone .local/examplechannel/apple-full.yaml --check
uv run --extra vlm python - <<'PY'
from PIL import Image
from minnarone.video import VideoFrame
from minnarone.vlm import Qwen2VlCaptioner, QwenVlConfig

image = Image.open(".smoke/p1-video/raw/video/video-0001.jpg").convert("RGB")
captioner = Qwen2VlCaptioner(QwenVlConfig(
    model=".local/models/qwen2-vl-2b/895c3a49bc3fa70a340399125c650a463535e71c",
    device="mps", device_map=None, quantization=None,
))
print(captioner.caption(VideoFrame(pixels=image, source_label="smoke", ts=0)))
PY
```

P4 CUDA full:

```bash
nvidia-smi
uv sync --extra audio --extra video --extra vlm --extra tui
uv run minnarone .local/examplechannel/cuda-full.yaml --check
uv run --extra vlm python - <<'PY'
from PIL import Image
from minnarone.video import VideoFrame
from minnarone.vlm import Qwen2VlCaptioner, QwenVlConfig

image = Image.open(".smoke/p1-video/raw/video/video-0001.jpg").convert("RGB")
captioner = Qwen2VlCaptioner(QwenVlConfig(
    model=".local/models/qwen2-vl-2b/895c3a49bc3fa70a340399125c650a463535e71c",
    device="auto", device_map="auto", quantization="4bit",
))
print(captioner.caption(VideoFrame(pixels=image, source_label="smoke", ts=0)))
PY
```

P5 llama.cpp full usa il bundle Gemma pinned già misurato:

```bash
uv sync --extra audio --extra video --extra vlm-llamacpp --extra tui
# Terminale A: lasciare il server attivo.
llama-server \
  -m .local/models/gguf/gemma-4-e2b/66a399f68ddd113b06dff02fca9523e55465d11d/gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf \
  --mmproj .local/models/gguf/gemma-4-e2b/66a399f68ddd113b06dff02fca9523e55465d11d/mmproj-F16.gguf \
  --port 8080 -ngl 99 -c 16384 --parallel 2 --reasoning off
# Terminale B, dopo il caricamento del modello.
curl --fail http://127.0.0.1:8080/health
curl --fail http://127.0.0.1:8080/props
uv run minnarone .local/examplechannel/llamacpp-full.yaml --check
```

La variante Qwen2-VL sostituisce i due path Gemma con il GGUF Q4_K_M e il
`mmproj` Q8_0 pinned nel manifest; resta sperimentale finché ripete con successo
`/health`, `/props`, caption e shadow sullo stesso hardware.

Dopo i model smoke, esercitare realmente code, stats e fallback con config che
impostano `twitch.send.mode: shadow`. Lasciare ogni run attivo per una finestra
decisa (per esempio 60 secondi), quindi fermarlo con Ctrl-C; non premere `p`:

```bash
uv run minnarone .local/examplechannel/cpu-audio.yaml --tui
uv run minnarone .local/examplechannel/apple-full.yaml --tui
uv run minnarone .local/examplechannel/cuda-full.yaml --tui
uv run minnarone .local/examplechannel/llamacpp-full.yaml --tui
```

Su Linux usare `sha256sum` al posto di `shasum -a 256`.

## Smoke di accettazione

Ordine comune:

1. `minnarone <config> --check`;
2. chat smoke;
3. raw audio/video separati;
4. ASR su un PCM salvato;
5. speaker embedding (dimensione 512 e norma circa 1);
6. caption di un frame salvato;
7. shadow bounded con code/stats visibili;
8. live solo dopo i guardrail del ticket 14.

Per P3/P4 il primo frame è il vero gate VLM: `--check` può passare anche se
pesi, CUDA/MPS o memoria falliranno. Per P5 servono `/health` e `/props`, e il
server multimodale usa `--mmproj`; con `--parallel 2` il contesto è diviso tra
gli slot.

## Evidenza e limiti

- Il run CUDA interno ha validato Windows 11, RTX 500 Ada 4 GB, ASR
  large-v3-turbo CPU int8 e Qwen2-VL-2B NF4: circa 1.5 GB VRAM, 3.5 s per
  caption warm e circa 60 s cold load.
- Il run llama.cpp interno ha validato build b10016 e il GGUF/mmproj indicato:
  circa 1.47 GB VRAM per testo e 2.4–2.7 GB multimodale.
- Gli hash dei vecchi file locali non furono registrati; i digest qui sopra
  identificano artifact upstream correnti, non retroattivamente quei run.
- Nessun minimo Apple Silicon o CPU è stato misurato da clone pulito. I budget
  P2/P3 sono conservativi e devono essere verificati dal prototipo 16.
- `uv.lock` risolve oggi una versione Transformers più nuova dell'ambiente
  registrato nelle prove; il ticket 16 deve conservare anche il lock Python nel
  transcript.

## Fonti

Tutte consultate il 2026-07-18.

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — runtime e
  licenza MIT.
- [Snapshot faster-whisper large-v3-turbo](https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo/tree/0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf)
  — revision e pesi CTranslate2.
- [3D-Speaker](https://github.com/modelscope/3D-Speaker) — owner, versioni e
  licenza Apache-2.0 dei modelli CAM++.
- [Release speaker sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx/releases/tag/speaker-recongition-models)
  e [checksum ufficiali](https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/checksum.txt).
- [Qwen2-VL-2B-Instruct pinned](https://huggingface.co/Qwen/Qwen2-VL-2B-Instruct/tree/895c3a49bc3fa70a340399125c650a463535e71c)
  — model card, Apache-2.0 e shard.
- [Qwen2-VL-2B-Instruct GGUF pinned](https://huggingface.co/ggml-org/Qwen2-VL-2B-Instruct-GGUF/tree/bb307c036e8a1ed7b663bbd0c35b41c4c9294cfd)
  — variante Q4_K_M e mmproj per llama.cpp.
- [llama.cpp](https://github.com/ggml-org/llama.cpp) e
  [release b10016](https://github.com/ggml-org/llama.cpp/releases/tag/b10016) —
  runtime MIT, revision e digest degli asset.
- [Gemma 4 E2B GGUF pinned](https://huggingface.co/unsloth/gemma-4-E2B-it-qat-GGUF/tree/66a399f68ddd113b06dff02fca9523e55465d11d)
  — GGUF/mmproj e licenza Apache-2.0 dichiarata dal model card.
- [`pyproject.toml`](../../pyproject.toml), [`uv.lock`](../../uv.lock),
  [guida operatore](../twitch-operator.md),
  [example llama.cpp](../../examples/llamacpp-local.example.yaml), run di
  accettazione [full Twitch](../issues/local-twitch-perception-runtime/done/12-full-twitch-commentator-acceptance-run.md)
  e [speaker HITL](../issues/speaker-diarization-over-segmentation/done/05-hitl-accettazione-diarizzazione-live.md).

## Next step

Il ticket 16 deve prototipare il manifest e `minnarone-runtime-doctor` sui
profili P0, P2 e almeno uno fra P3–P5, senza download implicito o live.

Per il fold nel parent spec:

- **Ticket 15 — profili runtime definiti** (2026-07-18): sei profili
  progressivi separano chat-only, capture, CPU audio, Apple Silicon, CUDA e
  llama.cpp; ogni profilo dichiara extra, tool, modelli, budget e smoke.
- **Modelli ripetibili**: ASR, CAM++ English 512, Qwen2-VL-2B e GGUF/mmproj
  hanno owner, licenza, revision e SHA-256; il vecchio CAM++ zh-cn 192 non è più
  raccomandato per italiano. Il ticket 16 proverà docs + manifest +
  `minnarone-runtime-doctor`, senza download multi-GB impliciti.

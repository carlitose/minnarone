# Prototipo onboarding per code agent e umano

## Domanda e branch

**Domanda:** qual è il minimo insieme di tutorial, skill repo-local e CLI che
porta un code agent e una persona normale da clone pulito a `--check` e shadow,
senza inventare persona/facts, nascondere prerequisiti o promuovere live?

**Branch del prototipo:** logica/workflow. Gli artifact usa-e-getta vivono in
[`spike/onboarding_surface/`](../../spike/onboarding_surface/). Nessun codice è
integrato in `src/minnarone`.

## Ipotesi e stop rule

Conservare una nuova superficie solo se intercetta tutti i dieci errori seeded
e riduce almeno due passaggi evitabili, senza duplicare il contratto canonico in
docs, skill e CLI. Hard gate: zero invii live, segreti, overwrite silenziosi o
scritture prima della conferma.

## Artifact provati

- `onboarding.py`: intervista/preview deterministica; richiede tutte le domande
  del ticket 13 e un digest della preview Markdown esatta prima di scrivere.
- `doctor.py` + `manifest.json`: check read-only PASS/FAIL di profilo, tool,
  revision, SHA-256, dimensione speaker e guardrail Twitch.
- skill prototype `minnarone-twitch-onboarding` e
  `minnarone-runtime-doctor`, col naming deciso nel ticket 10 e il confine
  esplicito verso `minnarone-prompts` rinominata nel ticket 11.
- fixture sanitizzate, confronto machine-readable e 19 test in directory
  temporanee.

I file esistenti producono un diff e richiedono `--allow-update` oltre alla
conferma del digest. `## Contesto corrente` è rifiutato senza opt-in. Dopo la
scrittura il prototipo propone solo `validate-prompts` e `--check`, poi si
ferma.

## Scenari eseguiti

| Scenario | Evidenza | Esito |
| --- | --- | --- |
| Code agent, nuovo canale | Skill onboarding + fixture con origini `operator`/`verified_metadata`; preview digest `0e4c30…`; nessun flag di conferma | PASS: `NO_WRITE`, nessun `.local/` creato |
| Code agent, conferma esatta | Stessa preview con digest esatto | PASS: `soul.md` e un facts file creati sotto `.local/examplechannel/` |
| File esistente | `soul.md` user-owned diverso | PASS: diff mostrato, exit 2 e contenuto preservato senza `--allow-update` |
| Risposta mancante | Campo persona `tone` rimosso | PASS: errore prima di qualunque write |
| Umano/tutorial fino a check | File confermati + template shadow sanitizzato + env dummy non segreto | PASS: vero `minnarone <config> --check`, exit 0 |
| P0 doctor | Nessun modello, guardrail espliciti | PASS; next step è check e shadow TUI, mai live |
| P2 doctor | Tool fake isolato + artifact pinned 512 | PASS; la stessa fixture con dimensione 192 fallisce prima del runtime |
| P5 doctor | Tool fake + GGUF/mmproj piccoli con revision/digest pinned | PASS della logica doctor senza scaricare pesi reali |
| Shadow offline | `PublicSendPolicy` produzione con mode shadow | PASS: decisione `shadow`, `promote()` rifiutata |
| Live accidentale | scenario doctor con `send_mode: live` | PASS del guardrail: report FAIL |

La prova P2/P5 verifica il contratto del doctor, non hardware o qualità dei
modelli. Nessun peso, server, stream o endpoint Twitch è stato avviato.

## Confronto delle superfici

I “passaggi” e le duplicazioni sono **stime** ricavate dagli item espliciti
nelle checklist umano/agent, non tempi osservati su partecipanti. “Errori evitati”
deriva ora da dieci probe eseguibili dei ticket 12–15: persona incompleta, write
prematuro, contesto persistito, token shadow, promozione live, consenso,
retention inerte, speaker 192, digest modello e lazy VLM. Il tutorial viene
ispezionato per i guardrail che può solo spiegare; le due superfici guidate
eseguono gli stessi probe enforcement, dando al CLI combinato il best case.
“Duplicazione” conta regole ripetute fuori dalla fonte canonica. Il vincitore è
calcolato fra le superfici che passano tutti i probe, minimizzando prima la
duplicazione e poi i passaggi totali.

| Superficie | Passi umano stimati | Passi agent stimati | Errori evitati (probe) | Regole duplicate stimate |
| --- | ---: | ---: | ---: | ---: |
| Tutorial + template soltanto | 15 | 15 | 5/10 | 0 |
| Skill unica + `minnarone init/doctor` core | 7 | 7 | 10/10 | 5 |
| Due skill sottili + docs/manifest | 8 | 7 | 10/10 | 1 |

Il CLI core risparmia un solo passaggio umano rispetto alle due skill, nessuno
per il code agent, ma duplica cinque contratti ancora in evoluzione. Il tutorial
da solo resta necessario per l'umano, ma non applica il gate conversazionale e
manca metà degli errori seeded.

## Scelta

Promuovere nel ticket 17:

1. tutorial task-first e template per l'utente normale, con docs come fonte
   canonica;
2. skill repo-local `minnarone-twitch-onboarding`, sottile e human-gated;
3. skill repo-local `minnarone-runtime-doctor`, read-only, che usa un manifest
   versionato e restituisce PASS/FAIL/SKIP;
4. `minnarone-prompts` resta separata e gestisce solo prompt template/override.

Non costruire ora `minnarone init` o `minnarone doctor` in produzione. La logica
deterministica potrà essere promossa nel core solo dopo che due flussi reali
mostreranno un vantaggio per utenti senza code agent. Eliminare gli script e le
fixture spike dopo la produzione delle superfici definitive.

## Limiti

- Il percorso umano è una walkthrough del tutorial/template con `--check`
  reale, non un usability test con un secondo partecipante.
- P2/P5 usano byte e tool fake per testare digest/revision/dimension; i model
  smoke hardware restano quelli prescritti dal ticket 15.
- La prova shadow è offline sulla policy produzione; non apre chat o Streamlink
  e non misura durata/qualità di una live.
- `announce_ai` e retention restano gap runtime del ticket 18; il prototipo li
  segnala e non li dichiara risolti.

## Comandi verificati

```bash
uv run python -m unittest discover -s spike/onboarding_surface -p 'test_*.py'
uv run python spike/onboarding_surface/compare.py
```

Esito: 19 test passati; scelta `two_thin_skills_and_docs`, 10/10 trap
intercettate, 7 passi agent stimati e 8 passi umano stimati.

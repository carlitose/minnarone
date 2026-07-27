# Minnarone launch kit

> Approved deliverable for
> [repo-promotion ticket 05](../tickets/repo-promotion/done/05-task-launch-kit.md).
> All public copy is English. The author approved the publishable copy and
> calendar on 2026-07-21. Publication remains out of scope until the GitHub
> storefront checklist is complete.

## Non-negotiable launch rules

- Link to <https://github.com/carlitose/minnarone>; the repository is the
  landing page.
- Attach `docs/assets/minnarone-tui-demo.gif` natively where the platform
  supports media uploads.
- Describe the Enkk connection only as inspiration. Minnarone is independent;
  Enkk is not affiliated with it and must never be tagged or presented as an
  endorser.
- Never ask for votes, stars, likes, reposts, or coordinated comments.
- Say that 4 GB is a measured NVIDIA configuration, not a universal minimum.
- Say that perception is local by default and that fully local text plus vision
  is an available llama.cpp profile, not the only configuration.
- Say `shadow` when the demo does not send to Twitch. Do not imply that
  `--check` proves hardware, network, or first-inference readiness.

## Show HN

Submission URL: <https://github.com/carlitose/minnarone>

Title:

> Show HN: Minnarone – Multimodal agents that watch, listen, and react live

First comment:

> I built this Minnarone framework after seeing a video by streamer Enkk about
> a Twitch bot that could participate naturally in chat. This repository is an
> independent open-source generalization of that idea; Enkk is not affiliated
> with it.
>
> The core loop turns live chat, audio, and video into timestamped perceptions,
> maintains short-term context, decides when a reaction is useful, and routes
> the result to a public or private output. The perception side is local:
> faster-whisper for ASR, sherpa-onnx for speaker embeddings, and a VLM for
> frames. The LLM can be remote, or text and vision can share one local
> llama.cpp server. A specific full profile has been measured on a 4 GB NVIDIA
> GPU; that is a validated configuration, not a general minimum.
>
> The quickest path is deliberately less ambitious: a chat-only shadow run
> that generates candidate replies without sending them. Full multimodal and
> attended live paths are staged behind explicit checks. Even a live-configured
> session starts in shadow and needs manual promotion from the TUI; it also has
> a separate write token, allow-list, budgets, and a kill switch.
>
> The 30-second GIF at the top of the README is a real English shadow run. The
> core runtime, dashboard, replay, Twitch adapter, OS-capture meeting profiles,
> and safety gates are implemented; the README links an honest roadmap for the
> remaining work.
>
> Minnarone is MIT licensed. I am especially interested in people trying the
> shadow workflow and reporting setup friction, latency, or results on hardware
> profiles I have not measured yet.

Posting notes:

- Submit the repository URL, then add the first comment immediately.
- Be available for the full first hour. Do not ask anyone to upvote it.
- Attach no separate media to HN; the GIF is already prominent in the README.

## X thread

Attach the demo GIF to post 1. Put the repository link in post 2.

1. > I open-sourced Minnarone: a Python framework for agents that watch,
   > listen, and react to live context. This 30-second Twitch shadow run turns
   > chat, speech, and video into a candidate reply without sending it.

2. > The loop is modular: chat/audio/video → timestamped perceptions → memory
   > and triggers → reaction → output routing. Local ASR uses faster-whisper,
   > speaker embeddings use sherpa-onnx, and frames go through a VLM.
   > https://github.com/carlitose/minnarone

3. > It can use a remote LLM with local perception, or serve text and vision
   > through one local llama.cpp process. The measured P5 bundle ran on a 4 GB
   > NVIDIA GPU; that is a validated setup, not a universal hardware promise.

4. > Safety is part of the runtime: the quickstart is shadow-first. A
   > live-configured session still starts in shadow, needs manual TUI promotion,
   > uses a separate write token and allow-list, and has a kill switch.

5. > Minnarone was inspired by a video from streamer Enkk. This is an
   > independent project; he is not affiliated with it. v0.1.0 is MIT licensed.
   > I’m looking for people to try the shadow workflow and report setup friction
   > or hardware results.

Posting notes:

- Use no more than one hashtag; the recommended default is no hashtag.
- Do not add the GitHub link to post 1; the repository name is already visible
  in both the copy and GIF.

## LinkedIn

Upload the demo GIF natively. Put the repository URL in the first comment.

Post:

> I’ve open-sourced Minnarone, a Python framework for agents that perceive live
> chat, speech, and video, then decide when and how to react.
>
> It grew from an idea I saw in a video by streamer Enkk. Minnarone is my
> independent generalization; Enkk is not affiliated with the project.
>
> The runtime separates local ASR, speaker embeddings, video captioning,
> timestamped perceptions, memory, triggers, and guarded output. It can pair
> local perception with a remote LLM, or serve text and vision through one
> llama.cpp process. One pinned full profile was measured on a 4 GB NVIDIA GPU.
>
> The demo is a shadow run: Minnarone creates a candidate reply but sends
> nothing. The quickstart uses the same shadow-first path; live output requires
> manual promotion and keeps a kill switch.
>
> v0.1.0 is MIT licensed. I’d value reports from developers who try the
> quickstart: where setup is unclear, what latency you see, and which hardware
> profile you use.

First comment:

> Repository, demo, and quickstart:
> https://github.com/carlitose/minnarone

## Reddit: r/SideProject

This is the publishable Reddit fallback because r/SideProject does not ban
AI-assisted copy. Use a text post and embed the demo GIF.

Title:

> Minnarone - Multimodal agents that watch, listen, and react to live context

Body:

> I built and open-sourced this Minnarone framework for agents that turn live
> chat, audio, and video into contextual reactions.
>
> The architecture separates adapters, local perception, short-term memory,
> reaction triggers, LLM providers, and guarded output routing. It supports a
> chat-only shadow quickstart, a full multimodal Twitch path, and private local
> meeting-assistant profiles. Text and vision can share a local llama.cpp
> server; one pinned full configuration has been measured on a 4 GB NVIDIA GPU.
>
> The attached GIF is a real shadow run. It shows the agent building context
> from chat, transcription, and video captions before producing a candidate
> reply. Nothing is sent to Twitch.
>
> The project was inspired by a video from streamer Enkk, but it is independent
> and he is not affiliated with it. Minnarone v0.1.0 is MIT licensed.
>
> Repository and quickstart:
> https://github.com/carlitose/minnarone
>
> I am looking for practical feedback from people who try it: setup friction,
> latency, confusing documentation, and results on other hardware profiles.

## Reddit: r/LocalLLaMA author worksheet

Do **not** publish generated prose verbatim in r/LocalLLaMA. Its rules prohibit
primarily LLM-generated post text. The author must write the title and body in
their own words, using the fact bank below; an agent may later check technical
accuracy without rewriting the author's voice.

Required structure:

1. State plainly that you built and maintain this Minnarone framework.
2. In two or three personal sentences, explain why you generalized a live
   Twitch bot into a reusable agent framework.
3. Explain the pipeline in your own words: live chat/audio/video → local
   perception → context and triggers → reaction → guarded output.
4. Describe the two LLM paths: remote LLM with local perception, or a single
   llama.cpp process for local text and vision.
5. State the measured 4 GB NVIDIA result as one validated configuration, not a
   hardware minimum.
6. Explain that the attached GIF and quickstart are shadow runs and send
   nothing.
7. Add the factual attribution: inspired by a video from streamer Enkk;
   independent project; no affiliation.
8. Ask for concrete setup, latency, model, and hardware feedback. Do not ask
   for votes or stars.
9. Link the repository and disclose authorship. Use `Resources` or `Other`
   flair, subject to the live posting UI.

## Prepared answers for the first 72 hours

### Is it really fully local?

> It can be. Perception is designed to run locally. You can pair it with a
> remote reaction LLM, or use the P5 llama.cpp profile where one local server
> handles text and vision. I describe the exact model artifacts and revisions
> in the runtime profile docs rather than treating “local” as a blanket claim.

### Does it really run on a 4 GB GPU?

> A specific Windows/NVIDIA configuration was measured successfully: the P4
> Qwen profile and the P5 pinned Gemma llama.cpp bundle have 4 GB validation
> evidence. That does not make 4 GB a universal minimum. Model choice, context,
> frame rate, concurrency, RAM, and backend all matter, so the docs separate
> measured results from planning envelopes.

### Does the quickstart post to Twitch?

> No. The quickstart is chat-only shadow mode: it reads chat and records
> candidate replies locally. It does not read a write token or send messages.
> Live output is a later, attended path with broadcaster consent, a dedicated
> bot account, an allow-list, separate write credentials, manual promotion, and
> a kill switch.

### What is implemented versus planned?

> The core runtime is implemented: Twitch chat/audio/video perception,
> shadow/live routing, local commentary and meeting-assistant profiles,
> observability TUI, replay, configurable providers, prompts, soul, and facts.
> The README links the project specification and labels later roadmap items
> instead of presenting them as shipped.

### What data does shadow mode keep?

> Shadow prevents public sending, but it is not a no-data mode. A run can store
> perceptions, prompts, debug events, summaries, and derived chat locally. The
> current retention-days field is reserved rather than an automatic deletion
> guarantee, so operators must use purpose-bound retention and delete complete
> run directories and derived copies when required.

### Is this Enkk's project?

> No. Minnarone was inspired by an idea shown in a video by streamer Enkk, but
> it is an independent project. He is not affiliated with it and is not
> involved in its maintenance.

### What feedback is most useful?

> Reproducible reports from the shadow workflow: operating system, hardware,
> selected runtime profile, models, first-inference time, steady latency, queue
> behavior, and the exact setup step that failed or was unclear. Real users and
> actionable issues are more useful to me than star counts.

## Proposed launch calendar

All local times below are Europe/Madrid summer time (CEST, UTC+2). Each post is
scheduled at the beginning of the author's one-hour availability window.

| Date | Local time | Action | One-hour focus |
| --- | --- | --- | --- |
| Sat 2026-07-25 | 18:00 | Day 0 gate: merge launch-kit PR, complete the social preview/card check, verify README and native GIF uploads, and confirm all accounts are ready. | Do not launch if ticket 02 remains open. |
| Sun 2026-07-26 | 17:00 | Submit Show HN; immediately add the prepared first comment. Publish the X thread at about 17:15. | HN replies first, then X replies. One optional HN check later that day if time permits. |
| Mon 2026-07-27 | 10:00 | Publish LinkedIn with native media. Publish r/LocalLLaMA only if the author-written post is ready and current account/rules checks pass. | LinkedIn, Reddit, then HN stragglers. |
| Tue 2026-07-28 | 10:00 | Publish r/SideProject if r/LocalLLaMA was skipped; otherwise hold it for week 2 to avoid campaign-like Reddit behavior. | Reddit replies and cross-channel issue triage. |
| Sun 2026-08-02 or later | 09:00 | Optional second Reddit post, rewritten for that community, only if account history and the first launch response justify it. | Never native-crosspost identical copy. |

## Author approval checklist

- [x] Show HN title and first comment approved.
- [x] X thread approved.
- [x] LinkedIn post and first comment approved.
- [x] r/SideProject title and body approved.
- [x] Exact calendar approved.
- [x] r/SideProject selected as the launch Reddit channel. r/LocalLLaMA remains
      an optional later channel and still requires author-written copy.

Approval recorded from the author in chat on 2026-07-21: “Approvo tutto”.

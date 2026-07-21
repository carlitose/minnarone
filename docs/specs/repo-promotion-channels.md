# minnarone — Launch Channel Map (HN, Reddit, X, LinkedIn)

> Deliverable of ticket [repo-promotion/04](../tickets/repo-promotion/done/04-research-channel-rules.md).
> Research date: 2026-07-21. Subreddit rules were read directly from each
> subreddit's live rules page (via old.reddit.com) on that date. Where a claim
> could not be verified against a primary source, this is stated explicitly.
> In English because it quotes English-language sources and feeds English
> launch material.

## 1. Hacker News / Show HN

### Official rules (news.ycombinator.com/showhn.html)

- Show HN is for "something you've made that other people can play with" —
  things people can run on their computers. minnarone (a `pip`-installable
  framework with a runnable demo) qualifies.
- The title must start with `Show HN:`. Posts appear on `shownew` and move to
  the `show` page after a small points threshold.
- The project must be **non-trivial** ("Don't post quickly-generated
  one-offs"), must be **your own work**, and — critical for the availability
  constraint — **"you should be available to discuss it in the thread."**
- Not allowed as Show HN: blog posts, sign-up pages, landing pages,
  fundraisers. Avoid signup/email barriers to trying it.
- Unpolished/early-stage is explicitly fine ("needn't be complicated or look
  slick").

### Flagging / bans (news.ycombinator.com/newsfaq.html)

- Posts get `[flagged]`/`[dead]` via user flags, anti-abuse software, or
  moderators.
- **Asking anyone for upvotes or comments is prohibited** and penalized — HN
  "will penalize or ban submissions, accounts, and sites"; voting-ring
  detection filters votes (Lucas Costa's retrospective confirms these votes
  don't count).
- **Reposting is allowed**: "If a story has not had significant attention in
  the last year or so, a small number of reposts is ok." A flopped first
  attempt can be retried later.
- Ranking = points / power of time, plus flags, anti-abuse, "overheated
  discussion" demotion, and moderator action. Karma does not boost ranking.

### Title format (from guidelines + retrospectives)

- Direct, specific, technically descriptive; no marketing language. Good
  pattern per Lucas Costa: `Show HN: <Name> – <plain technical description>`.
  Candidate: `Show HN: Minnarone – Local multimodal agents that watch, listen
  and react in real time` (with the "runs on a 4 GB GPU" hook in the title or
  first comment — retrospectives note concrete resource claims perform well).
- Link the **GitHub repo, not a landing page** — "the repo *is* the landing
  page," and stars spread via GitHub's network effects.

### Best day/time (credible analyses — they partially disagree)

- **Daniel King, "Show HN by the Numbers" (188,085 Show HN posts,
  2012–2026)**: best slot Monday 00:00 UTC (= Sunday 7pm ET) with 10.8% chance
  of 50+ points; also Sunday 02:00 UTC (9.8%) and Saturday 19:00 UTC (9.2%).
  Worst: Thursday 06:00 UTC (2.6%). Median Show HN gets 2 points; ~28,000
  Show HN posts/year now.
- **ankle.io (13,159 posts)**: best front-page probability 06:00–12:00 UTC;
  overall front-page rate ~3.2%; Show HN posts reach the front page slightly
  *less* often proportionally than regular links.
- **chanind.github.io (2018–19 BigQuery)**: weekends/off-peak UTC maximize
  front-page probability; weekday US mornings maximize traffic if you do hit
  the front page.
- **Lucas Costa** (successful launcher): "there is no ideal posting time" —
  the upvote-to-competition ratio is roughly constant; quality dominates.
- Net: weekend/Sunday posting trades peak traffic for lower competition — a
  good trade for a solo maintainer.

### Risk with ~1h/day comment availability: HIGH, but manageable

- The official guideline explicitly expects you to be available to discuss.
  Retrospectives (Lucas Costa, NebulaGraph) describe engaging throughout the
  day; unanswered questions stall momentum.
- However, King's data shows **92% of the GitHub-star impact happens within
  48h** and the spike is Day 1 — which fits the 72h monitoring window *if*
  the post goes up at the *start* of the daily availability hour.
- Mitigations: (a) post at the moment the 1h window begins; (b) immediately
  add a substantive first comment (architecture, why local-only, the 4 GB GPU
  constraint, honest limitations — HN rewards candor); (c) pre-answer FAQs in
  the README so the thread self-serves; (d) pick the Sunday slot, when thread
  velocity is slower and 2 check-ins/day cover more of the conversation.

### Documented lessons from launches (open-source / AI-agent projects)

1. **"Show HN by the Numbers" — Daniel King (2026)**: median is 2 points, so
   treat HN as a lottery ticket with prepared collateral; ~1.4 GitHub stars
   per upvote within 48h; "A Show HN launch is not a growth strategy. It's a
   pulse" — README and demo must be polished *before* posting because there is
   no second day.
2. **Lucas Costa (Layerform, open-source dev-tool, front page)**: link the
   repo not a landing page; README with images; cut marketing-speak (~30% of
   words); never solicit votes — detection is excellent; engage in comments
   all day.
3. **fastagi/MLE-Agent ("8 Lessons from our #2 GitHub Trending LLM Agent")**:
   ride the current wave (agents) but target a specific user; README modeled
   on top projects **with an honest roadmap separating done vs. planned**;
   ship a small fix daily post-launch to stay visible to GitHub trending.
4. **NebulaGraph front-page retrospective**: front page with zero vote
   solicitation brought 300+ stars in 24h — plain technical title.

## 2. Reddit

Sitewide baseline (reddit.com/wiki/selfpromotion): ≤10% of your activity
should be your own links; never upvote-solicit (account/domain bans); "It's
perfectly fine to be a redditor with a website, it's not okay to be a website
with a reddit account." Participate genuinely before/around the launch.

### Verified best-fit subreddits (rules read 2026-07-21)

**r/LocalLLaMA — best fit (primary channel)**

- On-topic = LLMs (a local multimodal llama-server agent framework is
  squarely on-topic); Rule 4 "Limit Self-Promotion": 1/10 rule, **affiliation
  must be disclosed**, no engagement-farming framing ("I found this…" posts by
  the author are banned — post honestly as the author); Rule 3: **no primarily
  LLM-generated post text**.
- Format: text post, flair `Resources` or `Other`; technical details (VRAM,
  models used, faster-whisper/Qwen2-VL pipeline) are what this community
  engages with. Demo GIF/video embedded helps.
- Karma/age requirements: not documented in the public rules.

**r/opensource — good fit**

- Promo allowed with **`Promotional` flair** (Rule 8); repo **must have an
  OSI-listed license** (MIT ✓, Rule 4); Rule 2: <10% self-promo; Rule 6:
  **no drive-by posting** — you must engage in the comments of your own
  thread; Rule 3: AI-generated post text is ban-worthy.

**r/SideProject — good fit, lowest risk**

- No formal rules list (verified — empty rules page). Sidebar asks for format
  **"[Project name] - [Short description]"**. Self-promo is the sub's
  purpose. Lower technical depth of feedback.

**r/MachineLearning — conditional fit**

- "No Self-Promotion" **bans paid products but explicitly allows posts that
  "share a resource or collect feedback"** — a free MIT framework qualifies,
  at mod discretion; strict spam bans.
- Use `[P] Title` **and** the `Project` flair (the `[P]` tag is AutoModerator
  convention; the explicit written rule could not be found on the current
  public rules page).

### Verified poor fits (avoid or use special path)

- **r/Python — do NOT make a standalone post.** Rule 1 (current): AI
  showcases (multiple AI models / API wrappers) are **no longer allowed** as
  standalone posts — use the monthly showcase thread only (What My Project
  Does / Target Audience / Comparison structure).
- **r/artificial — marginal.** First post/comment cannot be promo; "We want
  participation here first"; modmail before posting. Skip unless the account
  has genuine history there.
- **r/Twitch — excluded without permission.** Rule 2F: no tools/apps/services
  **without prior mod permission** (modmail first); no link posts, body text
  required, English only.

### Cross-post spacing

- **No official Reddit rule specifies spacing between subreddits** (could not
  verify any documented number). Documented: sitewide spam guidance penalizes
  blasting the same link across subs; r/opensource and r/MachineLearning ban
  "campaign"-style behavior. Prudent practice: **one subreddit per day,
  rewriting the post for each community's angle**, never using the native
  crosspost button for promo.

## 3. X (Twitter) and LinkedIn

### X — format that works in 2025–2026

- **Lead with a native demo video/GIF**. Native media and threads get
  preferential distribution; analyses of the open-sourced algorithm
  (re-released Jan 2026) show the starter tweet gates distribution of the
  rest; 3–5-post threads gain materially more impressions than standalone
  posts (vendor analyses — treat numbers as directional).
- **Link placement — evidence contradictory and in flux**: the historical
  external-link penalty was **reportedly removed in October 2025**
  (tomorrowspublisher.today), but several 2026 analyses claim link posts
  still see ~30–50% less initial reach. Not resolvable against an X primary
  source. Safe pattern: hook + video in post 1, GitHub link in post 2 (or
  first reply), and say the repo name in the video/text.
- Hashtags: no evidence they help; 0–1 at most.
- Thread skeleton: (1) hook + demo video ("An open-source agent that watches
  your stream, hears the room, and answers in chat — fully local, 4 GB GPU"),
  (2) how it works (ASR + diarization + VLM + one llama-server), (3) why
  local/private (Teams-assistant use case), (4) inspiration credit stated as
  fact, (5) repo link + "MIT, contributions welcome".

### LinkedIn — format that works in 2025–2026

- Richard van der Blom's **Algorithm Insights Report** (1.8M+ posts): external
  links in the post body reduce reach (put the link in the first comment or
  use the "add link" sticker; a 2025 revision found short value-first captions
  *with* a link performing acceptably — the penalty is real but smaller than
  folklore says); text sweet spot ~800–1,000 characters; native video and
  document/carousel posts outperform; organic reach fell ~50% YoY — keep
  expectations modest.
- Effective shape: personal narrative ("I built and open-sourced…"), demo
  video uploaded natively, 3 short paragraphs (what it does, what's technically
  interesting, what feedback you want), GitHub link in first comment, 0–3
  hashtags.
- Comment velocity matters in the first 60–90 minutes — post at the start of
  the daily availability hour and reply to every comment within that hour.

## 4. Launch calendar (72h, ~1h/day)

Principle: one high-attention channel per day, posted at the **start** of that
day's 1-hour window. HN gets Day 1 because its impact half-life is 24–48h and
it feeds everything else.

| Day | Time (CET) | Action |
|---|---|---|
| **Day 0 (Sat)** | any | Freeze README (demo GIF at top, quickstart, FAQ, honest roadmap), record 60–90s demo video, pre-write all posts. |
| **Day 1 (Sun)** | ~08:00–10:00 CET (06:00–08:00 UTC) | **Show HN** (repo link + substantive first comment). Sunday morning UTC = documented low-competition window; aligns the thread's first hours with EU daytime, allowing a second check late evening. Right after: **X thread** (video first, repo in post 2). |
| **Day 2 (Mon)** | window start | **r/LocalLLaMA** (text post, disclosed authorship, technical write-up, demo GIF) + **LinkedIn** (native video, link in first comment — Mon/Tue mornings strongest). Spend the hour answering HN stragglers + Reddit first comments. |
| **Day 3 (Tue)** | window start | **r/opensource** (`Promotional` flair) *or* **r/SideProject** (`Minnarone - <short description>`) — pick one, hold the other for week 2. Reply pass on all open threads. |
| **Week 2+** | — | **r/MachineLearning** `[P]` post (feedback framing); r/SideProject leftover; r/Twitch **only after** modmail permission; r/Python monthly showcase comment only. If HN flopped (<5 points), one repost is permissible after significant time per the HN FAQ. |

Everywhere: mention Enkk only as factual inspiration ("inspired by a video by
streamer Enkk") — never "in collaboration with", no tagging/handle implying
endorsement, no "go ask him". Never solicit votes on any channel.

## Summary table

| Channel | Key rules | Format | Recommended slot | Risk (1h/day) |
|---|---|---|---|---|
| Hacker News (Show HN) | Tryable project, own work, be available in thread; no vote solicitation; repost OK after ~a year | `Show HN: Name – plain technical description`; link repo; substantive first comment | Sun 06:00–08:00 UTC or Sun 7pm ET | High — mitigated by window-start posting + FAQ-grade README |
| r/LocalLLaMA | 10% rule; disclose authorship; no LLM-written text | Text post + flair, deep technical detail, GIF | Day 2, EU morning | Low-medium |
| r/opensource | `Promotional` flair; OSI license required; no drive-by | Text post, license + architecture angle | Day 3+ | Low-medium |
| r/SideProject | No formal rules; format `Name - Short description` | Demo-and-story post | Day 3+ / week 2 | Low |
| r/MachineLearning | No paid-product promo; feedback-sharing at mod discretion | `[P]` tag + Project flair, feedback framing | Week 2 | Medium |
| r/Python | AI showcases banned as standalone posts | Monthly showcase thread comment only | Optional | N/A |
| r/artificial | Participation first; modmail before promo | Skip unless account has history | — | High |
| r/Twitch | Tools require prior mod permission | Modmail first | Only with permission | High without permission |
| X | Link-penalty status contested (reportedly removed Oct 2025) | 3–5-post thread, native video first, repo link in post 2/reply | Day 1, right after HN | Low |
| LinkedIn | Links in body reduce reach (van der Blom, 1.8M posts) | 800–1,000-char personal post, native video, link in first comment | Day 2, Mon morning | Low |

## Sources

**Hacker News**

- <https://news.ycombinator.com/showhn.html> (official Show HN guidelines)
- <https://news.ycombinator.com/newsfaq.html> (flagging, reposts, voting rings, ranking)
- <https://danfking.github.io/blog/2026/04/23/show-hn-by-the-numbers/> (188k Show HN posts)
- <https://www.ankle.io/posts/hacker-news-analysis/> (13,159-post timing analysis)
- <https://chanind.github.io/2019/05/07/best-time-to-submit-to-hacker-news.html>
- <https://www.lucasfcosta.com/blog/hn-launch> (launch retrospective, Layerform)
- <https://fastagi.substack.com/p/8-lessons-from-our-2-github-trending> (MLE-Agent lessons)
- <https://www.nebula-graph.io/posts/nebula-graph-being-on-hacker-new-front-page>
- <https://dev.to/dfarrell/how-to-crush-your-hacker-news-launch-10jk>

**Reddit** (rules read via old.reddit.com on 2026-07-21)

- <https://old.reddit.com/r/LocalLLaMA/about/rules>
- <https://old.reddit.com/r/MachineLearning/about/rules>
- <https://old.reddit.com/r/Python/about/rules>
- <https://old.reddit.com/r/opensource/about/rules>
- <https://old.reddit.com/r/SideProject/> (sidebar; empty formal rules page)
- <https://old.reddit.com/r/artificial/about/rules>
- <https://old.reddit.com/r/Twitch/about/rules>
- <https://old.reddit.com/wiki/selfpromotion> (sitewide 10% guideline)

**X / LinkedIn**

- <https://tomorrowspublisher.today/content-creation/x-softens-stance-on-external-links/>
- <https://ppc.land/how-xs-algorithm-silently-kills-your-links-without-explicitly-penalizing-them/>
- <https://opentweet.io/blog/how-twitter-x-algorithm-works-2026>
- <https://adlibrary.com/guides/x-twitter-algorithm-explained>
- <https://techcrunch.com/2026/01/20/x-open-sources-its-algorithm-while-facing-a-transparency-fine-and-grok-controversies/>
- <https://authoredup.com/blog/linkedin-algorithm> (van der Blom data summary)
- <https://mercermackay.com/thinking/blog/a-leaders-guide-to-the-linkedin-algorithm-what-the-data-says/>
- <https://www.dataslayer.ai/blog/linkedin-algorithm-february-2026-whats-working-now>

**Unverified items (stated as such above)**: exact `[P]`-tag written rule on
r/MachineLearning; any official Reddit cross-post spacing rule; karma/age
thresholds for the subreddits; resolution of the contradictory X link-penalty
reports (vendor blogs, not X primary sources).

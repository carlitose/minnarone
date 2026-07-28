# Relevant Twitch channels for a consented Minnarone canary

## Research Question

Which current Twitch channels are relevant and operationally suitable for one
consented, attended Minnarone canary, and which public route can the author use
to ask the broadcaster for permission without treating public chat as implied
authorization?

- Ticket:
  [twitch-consented-discovery/01](../tickets/twitch-consented-discovery/done/01-research-relevant-twitch-canary-channels.md)
- Parent spec:
  [twitch-consented-discovery.md](../specs/twitch-consented-discovery.md)
- Evidence date: **2026-07-28**
- Scope: public research only. No channel was contacted, joined, allow-listed,
  or sent a message.

## Answer

The strongest first-canary review set is:

1. **CodeWithTheItalians** — exact Italian live-coding fit, a current
   Europe/Rome calendar, and community scale.
2. **heidew1zzka** — community-sized live game-development stream, stable EU
   window, and an explicit creator-owned contact route.
3. **Naliore** — the clearest small-channel match for useful AI, automation,
   and current AI-native software work.
4. **MrDboy** — active game-development stream with an explicit business
   contact route and regular observed morning sessions.
5. **Brookzerker** — the most direct English AI/software match, including
   recent streams about AI agents playing or benchmarking games.

This is a review set, not an outreach list. Public contact links, permissive
link rules, other bots, or an open chat do not authorize Minnarone. Ticket 02
must choose the primary and backups; ticket 05 must later obtain explicit,
purpose-specific broadcaster approval.

## Hard Permission Boundary

Twitch's current cloud-chatbot model uses broadcaster authorization for a bot
acting through its own account. Platform terms prohibit unsolicited
advertising/spam, while the Developer Agreement requires understandable
identity and purpose, rejects deceptive or spam bots, and requires block,
discontinue, and opt-out handling.

For this pilot:

- a direct viewer question may qualify the *content* of a response only after
  the broadcaster has authorized the canary;
- a one-time, directly requested GitHub link is contextual, but Twitch
  documents no universal safe harbor for it;
- public chat, another bot, moderator/VIP status, successful IRC delivery, a
  public contact address, or absent custom rules are not permission;
- any ban, timeout, block, moderator/broadcaster stop, OAuth revocation, opt-out,
  or authorization uncertainty stops live sending immediately.

Primary platform sources:

- [Twitch Terms of Service](https://www.twitch.tv/p/en/legal/terms-of-service/)
- [Twitch Community Guidelines](https://www.twitch.tv/p/en/legal/community-guidelines/)
- [Twitch Developer Services Agreement](https://www.twitch.tv/p/en/legal/developer-agreement/)
- [Twitch Chat & Chatbots](https://dev.twitch.tv/docs/chat/)
- [Authenticating Chatbots](https://dev.twitch.tv/docs/chat/authenticating/)
- [Send and Receive Chat Messages](https://dev.twitch.tv/docs/chat/send-receive-messages/)
- [Twitch API Reference](https://dev.twitch.tv/docs/api/reference/)

These pages and the candidate sources below were accessed on 2026-07-28.

## Selection Rubric

The score is a prioritization aid, not permission:

| Dimension | Score | Evidence expected |
| --- | ---: | --- |
| Minnarone relevance | 0–3 | AI, software, automation, live coding, game development, or streaming-tool content |
| Conversational fit | 0–2 | Stream explicitly values questions, chat interaction, or participatory mechanics |
| Permission route | 0–2 | Broadcaster-designated business/contact route; a generic social link scores at most 1 |
| Visible bot/link compatibility | 0–2 | Current channel-specific rules; absence remains `unknown` |
| Attended schedule fit | 0–2 | Published or repeated observed window compatible with Europe/Madrid |
| Canary audience fit | 0–2 | Community/small audience preferred over a high-blast-radius first run |
| Moderation/safety risk | 0 to −2 | Fast/adversarial chat, automation ambiguity, schedule conflict, or other pilot risk |

Working reach bands use public follower counts only as an approximate discovery
proxy: community `<2k`, small `2k–10k`, lower-mid `10k–50k`, mid `50k–100k`,
and large `>100k`. A point-in-time live viewer count or VOD count is labelled
as such and is not treated as a stable concurrent-viewer average.

Recommended review candidates score at least 9, have relevance `3`, and have no
known rules conflict. Every candidate still has unresolved bot/link permission
until the broadcaster answers.

## Candidate Evidence

All schedule times below are UTC; add two hours for Europe/Madrid summer time
(CEST). “Observed” windows come from recent public VOD start times, not a
schedule promise.

| Candidate | Language and fit | Public activity / audience evidence | Window | Permission route | Bot/link rules | Score / disposition |
| --- | --- | --- | --- | --- | --- | --- |
| [CodeWithTheItalians](https://www.twitch.tv/codewiththeitalians/about) | Twitch setting EN; IT/EN Android, Kotlin and Compose live coding by two Italian creators. Exact technical and cultural fit. | 1,218 followers; latest observed VOD 2026-07-15. Community band. | [Schedule](https://www.twitch.tv/codewiththeitalians/schedule) and creator [calendar](https://codewiththeitalians.it/calendar-status.json): next observed slot 2026-07-29 16:30–18:00; biweekly, Europe/Rome. | Creator-owned [site](https://codewiththeitalians.it/) links the two public creator X accounts for a permission request. | Unknown. | **10 — recommended.** Resolve whether the public creator accounts are the preferred permission route. |
| [heidew1zzka](https://www.twitch.tv/heidew1zzka/about) | DE with some GER/EN titles; indie studio journey, coding and game-design discussion. | 712 followers and 34 live viewers at observation; recent VODs 276–615 views. Community band. | [Schedule](https://www.twitch.tv/heidew1zzka/schedule): Tue/Thu 09:00–12:00. | Creator-owned [Tiny Dragon Magic contact](https://www.tinydragonmagic.at/) and channel-linked Discord. | Unknown. | **11 — recommended.** Strong operational fit; confirm language for the canary. |
| [Naliore](https://www.twitch.tv/naliore/about) | FR; web development, useful AI, automation, and a current AI-native agency build. | 150 followers and 20 live viewers at observation; recent dev VODs 200–470 views. Community band. | No published schedule; observed July VOD starts range roughly 07:00–17:00. | Channel-linked creator [Discord](https://discord.naliore.fr/) and [GitHub](https://github.com/aurelien-altarriba). | Unknown. | **10 — recommended.** Best AI-specific small audience; French prompt readiness is a separate gate. |
| [MrDboy](https://www.twitch.tv/mrdboy/about) | EN; software/game development with active chat-facing channel commands. | 1,525 followers and 42 live viewers at observation; recent VODs 242–946 views. Community band. | No published schedule; recent starts were mostly 09:18–10:06, with one at 15:03. | Explicit business-inquiry email in Twitch About; channel-linked Discord and X. | External bots/links unknown; the channel's own commands are not authorization. | **10 — recommended.** Clear request route and active window. |
| [Brookzerker](https://www.twitch.tv/brookzerker/about) | EN; software development, leadership and productivity. Recent [VODs](https://www.twitch.tv/brookzerker/videos) include AI playing NetHack and AI benchmarking with Robocode. | 3,088 followers; latest observed VOD 2026-07-22. Small band. | Recent starts mostly around 16:00 on weekdays, with some 18:00–19:00 sessions. | Channel-linked Discord and creator [GitHub](https://github.com/BrooksPatton). | Unknown. | **10 — recommended.** Most direct English AI/software content fit. |
| [AdamCYounis](https://www.twitch.tv/adamcyounis/about) | EN; indie game development across code, engine/plugin work, pixel art, music and animation. Strong multimodal fit. | 50,591 followers. Mid band. | [Schedule](https://www.twitch.tv/adamcyounis/schedule): Mon/Tue/Thu/Fri 03:00–08:00; creator schedule agrees. | Studio [contact](https://upponhill.com/) exposes public contact addresses. | Visible rule: hyperlinks allowed with care; spam results in a ban. Bot permission unknown. | **12 — close alternate.** Excellent evidence and rules clarity, but early CEST window and larger blast radius. |
| [TheCodingBuddies](https://www.twitch.tv/thecodingbuddies/about) | DE; developer community across skill levels, currently Godot/coding. | 1,076 followers; two recent VODs observed at 517 and 473 views. Community band. | [Schedule](https://www.twitch.tv/thecodingbuddies/schedule): Tue 18:00–22:00. | Creator-owned [site](https://www.codingbuddies.de/) and public channel Instagram. | Unknown. | **10 — conditional alternate.** Good community fit; German prompt readiness and the permission route need confirmation. |
| [PlayPlump](https://www.twitch.tv/playplump/about) | EN; community Twitch idle pet/village builder controlled through chat commands. Strong interaction test but weaker host-conversation fit. | 211 followers and 14 live viewers at observation; recent VODs 76–278 views. Community band. | [Schedule](https://www.twitch.tv/playplump/schedule): Mon–Fri 06:30–22:30, start/end ±1 hour. | Channel-linked official Discord and public feedback form. | Own `!join`/game commands are invited; external bot/link policy unknown. | **9 — conditional.** Automation ambiguity makes this unsuitable before the identity/link policy is deterministic. |
| [T2sde](https://www.twitch.tv/t2sde/about) | EN; Linux/open-source development with current AI-for-open-source streams. | 10,755 followers and 79 live viewers at observation. Lower-mid band. | [Schedule](https://www.twitch.tv/t2sde/schedule): Tue 19:00–20:00, Thu 17:00–18:00, Sat 17:00–19:00. | Twitch About designates [exactcode.de](https://exactco.de/) as business contact. | Unknown. | **9 — later candidate.** Technically ideal, but a more adversarial AI-aware audience raises first-canary risk. |
| [AppleCoding](https://www.twitch.tv/applecoding/about) | ES; talks/interviews on Apple development and technology. | 5,726 followers; latest observed VOD 2026-07-08 with 211 views. Small band. | [Schedule](https://www.twitch.tv/applecoding/schedule): next observed slot 2026-08-01 17:00–19:00. | Channel and host public X accounts plus creator academy. | Unknown. | **8 — hold.** Interview format needs formal advance approval and a Spanish interaction contract. |
| [teej_dv](https://www.twitch.tv/teej_dv/about) | EN; Neovim core developer, original Telescope author, full-time live software building and learning with chat. | 44,707 followers. Lower-mid band. | Published [schedule](https://www.twitch.tv/teej_dv/schedule) says weekdays 14:00–20:00, but recent VOD starts did not match; recheck required. | Channel-linked official Discord and creator [GitHub](https://github.com/tjdevries). | Unknown. | **8 — hold.** Strong content fit, but schedule conflict and larger audience need resolution. |
| [bashbunni](https://www.twitch.tv/bashbunni/about) | EN; Go/Rust software development, open source, learning and chat banter. | 45,937 followers. Lower-mid band. | [Schedule](https://www.twitch.tv/bashbunni/schedule) showed 29–30 July sessions at 19:00–21:00; recent VODs mostly begin 19:00–20:00. | Business-inquiry address in About, creator [site](https://bashbunni.dev/), and official Discord. | Visible rules cover bullying and personal data; external bot/link policy unknown. | **8 — hold.** Excellent fit and contact, but a larger first-run blast radius. |
| [LowLevelTV](https://www.twitch.tv/lowleveltv/about) | EN; security engineering, Linux exploits, robotics and AI. | 28,099 followers. Lower-mid band. | Bio says Tue/Thu 10:00–12:00 “EST”; observed VOD starts 13:16–14:59, so timezone meaning must be confirmed. | Channel-linked X and creator-owned [Low Level Academy](https://lowlevel.academy/). | Visible rule is “Be excellent”; bot/link policy unknown. | **8 — hold.** High technical fit but security-sensitive audience and ambiguous window. |
| [Melkey](https://www.twitch.tv/melkey/about) | EN; Vercel staff engineer, former Twitch ML infrastructure engineer; recent AI/CLI/MCP themes. | 25,648 followers. Lower-mid band. | Published [schedule](https://www.twitch.tv/melkey/schedule) says Tue/Thu/Sat 00:30–05:30, but two recent VODs began around 17:40. | Channel-linked public X account. | Unknown. | **7 — hold.** Relevant but activity, contact specificity and schedule are not strong enough. |
| [Tsoding](https://www.twitch.tv/tsoding/about) | EN; recreational programming with recent Godot, ray-casting, parser and small-game work. | 83,552 followers. Mid band. | Nine of ten recent [VODs](https://www.twitch.tv/tsoding/videos) began around 16:53–17:15; frequency is irregular and the linked creator schedule is no longer reliable. | Official Discord and creator [GitHub](https://github.com/rexim). | Twitch ToS plus channel commands such as `!today`/`!faq`; external bot/link policy unknown. | **6 — exclude from first canary.** Audience and permission ambiguity outweigh reach. |

## Recommended Review Set

| Order | Candidate | Why now | Must resolve in ticket 02/05 |
| ---: | --- | --- | --- |
| 1 | CodeWithTheItalians | Closest match to the author's language/context and live-coding product audience; current calendar. | Exact permission route, custom rules, English vs Italian interaction contract. |
| 2 | heidew1zzka | Stable EU schedule, small live audience, explicit contact, genuine game-dev stream. | Accepted language and explicit bot/link scope. |
| 3 | Naliore | Strongest small-channel AI/automation content match. | French prompt readiness, irregular schedule, explicit broadcaster approval. |
| 4 | MrDboy | Explicit business contact and active community-sized game-development stream. | Published operating window and external bot/link rules. |
| 5 | Brookzerker | Strong English AI/software relevance and EU-compatible observed VOD window. | Broadcaster-designated permission path and current custom rules. |

Close alternatives are AdamCYounis when an early-morning CEST slot is acceptable,
and TheCodingBuddies when a German interaction contract is ready.

## Unknowns and Evidence Limits

- No candidate has authorized Minnarone.
- Twitch does not expose custom channel rules as a normalized public API field;
  `unknown` must be resolved during permission, not treated as permissive.
- Follower, live-viewer, VOD, category, and schedule observations change over
  time. Recheck the selected candidate immediately before outreach and live.
- A public Discord, social account, contact form, or business email is only a
  route for asking. The broadcaster must approve Minnarone's account, AI
  behavior, one-link cap, operating window, data handling, and immediate stop.
- French, German, Spanish, or Italian operation may require a validated prompt
  pack and language-specific shadow review. Ticket 01 does not claim that
  readiness.
- The public evidence supports channel selection only. It does not verify how
  the current Minnarone candidate behaves in any of these channels.

## Next Step

Run ticket 02 as HITL: the author selects one primary and ordered backups,
confirms the interaction language and exact disclosure/link trigger, and
approves the canary window and stop/success conditions. Do not contact a
candidate before that decision.

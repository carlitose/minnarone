# Minnarone launch log

> Execution record for
> [repo-promotion ticket 06](../tickets/repo-promotion/06-task-launch-and-monitor.md).
> Public copy lives in the approved
> [launch kit](repo-promotion-launch-kit.md). This file records actions,
> links, monitoring, metrics, and feedback; it is not publication authority.

## Launch status

- Phase: all four selected channels are published; launch follow-up remains
  incomplete until the preservation and 30-day metric checkpoints.
- Primary outcome: real users who try the framework and open useful questions
  or issues; stars alone are not success.
- Selected channels: Show HN, X, LinkedIn, and r/SideProject.
- r/LocalLLaMA is not in this launch because it requires author-written copy.
- Author availability: one focused hour per day during the first 72 hours.
- First public post: Show HN on Sunday 2026-07-26 at 17:10:49 CEST
  (15:10:49 UTC), after the final 17:00 CEST reschedule.
- Scheduled 72-hour checkpoint: Wednesday 2026-07-29 at 17:00 CEST; the exact
  72-hour boundary after the first post was 17:10:49 CEST and was also missed.
- 30-day checkpoint: Tuesday 2026-08-25 at 17:10:49 CEST.
- Schedule amended by the author on Saturday 2026-07-25 at 18:42 CEST:
  Sunday launch moved from 09:00 to 12:00 CEST; downstream checkpoints moved
  by the same three hours.
- Monday and Tuesday publication windows subsequently moved from 09:00–10:00
  to 10:00–11:00 CEST to match the author's availability.
- The Sunday 12:00 window was missed with no posts published. At 16:30 CEST
  the author moved Show HN to 17:00, X to 17:15, and confirmed monitoring
  availability through 18:00; downstream checkpoints moved by five hours.

## Late status reconstruction — Sunday 2026-08-02

The 72-hour checkpoint was not recorded at its scheduled time. A read-only
reconstruction at `2026-08-02T11:06:14Z` established the following without
presenting late observations as an on-time snapshot:

- Show HN, X, LinkedIn, and r/SideProject have canonical publication URLs and
  verified publication times. LinkedIn and r/SideProject were published after
  their planned windows but before this reconstruction.
- The four currently active stars were all created before the 72-hour
  boundary: one baseline star, two shortly after launch, and one at
  `2026-07-29T04:24:41Z`. No external issue or pull request was found across
  all states; the current fork count is zero.
- The current rolling Traffic window reports 175 views / 96 unique visitors
  and 136 clones / 72 unique cloners. These are late-window totals, not exact
  72-hour totals. The recoverable UTC rows for 2026-07-26 through 2026-07-28
  total 116 views, 86 view-unique-days, 11 clones, and 9 clone-unique-days.
- Current top referrers include Hacker News (14 views / 12 unique) and HN
  Algolia (6 / 2). LinkedIn reports 2 / 1, which is evidence of a visit, not
  evidence that the planned LinkedIn post was published.
- The official Hacker News item API still reports score 1 and no external
  discussion. At verification, LinkedIn reported 1,006 impressions, 3
  reactions, 2 comments, and 1 repost; r/SideProject reported 1 vote and 1
  comment. The LinkedIn author comment contains the GitHub link, while the
  other visible comment is generic and not actionable. No recurring product
  feedback is available to distill into a follow-up ticket.

## Baseline before launch

Captured from the authenticated GitHub REST API at
`2026-07-21T20:55:11Z`, before any scheduled launch post.

| Metric | Baseline |
| --- | ---: |
| Stars | 1 |
| Forks | 0 |
| External issues | 0 |
| External pull requests | 0 |
| Traffic views, rolling 14-day count | 80 |
| Traffic unique visitors, rolling 14-day count | 8 |
| Clones, rolling 14-day count | 74 |
| Unique cloners, rolling 14-day count | 25 |

Top pre-launch referrers were `github.com` (25 views, 4 unique) and
`web.telegram.org` (1 view, 1 unique). The repository overview had 27 views
from 7 unique visitors. These numbers already include maintainer and
pre-release activity and must not be attributed to the launch.

GitHub Traffic is a rolling 14-day window. Preserve daily arrays at every
checkpoint; totals from two distant snapshots cannot be subtracted safely.
Daily buckets use UTC midnight boundaries: the `2026-07-26` bucket contains
15 hours, 10 minutes, and 49 seconds before the 15:10:49 UTC launch and is only
partially attributable.
Counts can be summed after de-duplicating calendar dates across snapshots.
Daily `uniques` cannot be summed into a de-duplicated multi-day person count;
if summed, label the result `unique-day total`. Minnarone has no installation
telemetry, so unique clones and external questions/issues are proxies rather
than verified installations.

“External issues/PRs” means GitHub search results across all states and all
creation dates for `repo:carlitose/minnarone`, excluding items authored by the
repository owner account `carlitose`. This is reproducible but may include
bots or existing collaborators; inspect new items qualitatively before
claiming evidence of a new user.

### Raw baseline Traffic snapshot

Captured at `2026-07-21T20:55:11Z` from
`GET /repos/carlitose/minnarone/traffic/views` and
`GET /repos/carlitose/minnarone/traffic/clones`.

| UTC date | Views | View uniques | Clones | Clone uniques |
| --- | ---: | ---: | ---: | ---: |
| 2026-07-07 | 0 | 0 | 0 | 0 |
| 2026-07-08 | 0 | 0 | 0 | 0 |
| 2026-07-09 | 0 | 0 | 0 | 0 |
| 2026-07-10 | 0 | 0 | 0 | 0 |
| 2026-07-11 | 0 | 0 | 0 | 0 |
| 2026-07-12 | 0 | 0 | 0 | 0 |
| 2026-07-13 | 14 | 1 | 0 | 0 |
| 2026-07-14 | 3 | 1 | 0 | 0 |
| 2026-07-15 | 0 | 0 | 0 | 0 |
| 2026-07-16 | 0 | 0 | 0 | 0 |
| 2026-07-17 | 35 | 1 | 0 | 0 |
| 2026-07-18 | 10 | 1 | 0 | 0 |
| 2026-07-19 | 4 | 3 | 44 | 20 |
| 2026-07-20 | 14 | 4 | 30 | 13 |

## Day 0 gate — Saturday 2026-07-25 at 18:00 CEST

- [x] README has the 30-second demo GIF.
- [x] Repository description and topics are public.
- [x] Release `v0.1.0` is public.
- [x] Social preview is public and its remote hash matches the committed asset.
- [x] Launch copy and calendar are approved.
- [x] Author confirms access to HN, X, LinkedIn, and Reddit accounts.
- [x] Open the X, LinkedIn, and Reddit composers without publishing.
- [x] Confirm the native GIF can be selected from
      `docs/assets/minnarone-tui-demo.gif`. Show HN links the repository and
      uses the GIF already embedded in its README.
- [ ] Re-read the live platform rules and posting UI before each submission;
      if they conflict with the launch kit, stop rather than improvise.
- [x] Confirm the author can remain available during the launch monitoring
      windows: 17:00–18:00 CEST on Sunday and 10:00–11:00 CEST on Monday and
      Tuesday.

If any unchecked gate fails, move the calendar rather than publishing an
unattended or malformed launch.

## Publication record

The author publishes from their own accounts. Record the canonical URL and
time immediately after each action.

| Channel | Scheduled action | Published at | Canonical URL | Status |
| --- | --- | --- | --- | --- |
| Show HN | Sun 2026-07-26 17:00 CEST; add the approved first comment immediately | 2026-07-26 17:10:49 CEST | <https://news.ycombinator.com/item?id=49058933> | published; first comment verified |
| X | Sun 2026-07-26 about 17:15 CEST; native GIF on post 1, repo link on post 2 | 2026-07-26 17:20:24 CEST | <https://x.com/carlog_sergi/status/2081399240270459049> | published; first post and media verified |
| LinkedIn | Mon 2026-07-27 10:00 CEST; native GIF, repo link in first comment | 2026-07-27 11:26:02 CEST | <https://www.linkedin.com/feed/update/urn:li:activity:7487438139456917504/> | published; native GIF, post, and first-comment repository link verified |
| r/SideProject | Tue 2026-07-28 10:00 CEST; text post with embedded demo | 2026-07-28 13:46:48 CEST | <https://www.reddit.com/r/SideProject/comments/1v8w477/minnarone_multimodal_agents_that_watch_listen_and/> | published; public post, author, and converted MP4 verified |

Show HN verification: the official Hacker News API reported the approved title,
repository URL, and author `carlitose`; the first comment appeared at
2026-07-26 17:11:21 CEST as item `49058937`.

X verification: the official oEmbed endpoint reported author `Carlo Giuseppe`
(`@carlog_sergi`), the canonical status URL, and attached media on the first
post. The X snowflake timestamp resolves to 2026-07-26 17:20:24 CEST.

LinkedIn verification: the public post detail identifies activity
`7487438139456917504` and a publication time of 2026-07-27 11:26:02 CEST. At
the 2026-08-02 verification it reported 1,006 impressions, 3 reactions, 2
comments, and 1 repost. The author's first comment contains the GitHub link;
the other visible comment does not contain actionable Minnarone feedback.

r/SideProject verification: the public Reddit post identifies author
`u/carlitose86`, post `1v8w477`, and a publication time of 2026-07-28 13:46:48
CEST. At the 2026-08-02 verification it reported 1 vote and 1 comment, with no
recurring product-feedback theme to record.

Reddit publication was author-confirmed in chat by 2026-07-28 13:47:35 CEST.
r/SideProject did not permit inline images but allowed video, so the approved
30-second GIF was converted to an H.264 MP4 for the post. Unauthenticated
Reddit endpoints returned HTTP 403, so media and comment checks must use the
author's session.

Early launch milestone: at 2026-07-26 17:25:38 CEST the public GitHub API
reported 2 stars, 0 forks, and 0 open issues. Against the pre-launch baseline
of 1 star, this is the first attributable increase (+1 star); it is not a
replacement for the 72-hour checkpoint.

Second early milestone: at 2026-07-26 17:38:29 CEST the public GitHub API
reported 3 stars, 0 forks, and 0 open issues: +2 stars against the pre-launch
baseline.

Never solicit votes, stars, likes, reposts, or coordinated comments. Never tag
Enkk or imply affiliation. Do not substitute r/LocalLLaMA copy generated by an
agent.

## First-72-hour monitoring log

Use the prepared answers in the launch kit as factual scaffolding, then answer
the actual question in the author's voice. Record only recurring themes or
actionable product feedback here; do not copy private data or whole comment
threads into the repository.

| Window | Channel checks | Questions answered | Actionable themes / issue links |
| --- | --- | ---: | --- |
| Sun 2026-07-26 17:00–18:00 CEST | HN and X published; final HN/GitHub check at 18:00 CEST; author confirmed no X replies at 18:01 CEST; window closed | 0 | HN score 1 with no external replies; GitHub 3 stars (+2 from baseline), 0 forks, 0 open issues |
| Mon 2026-07-27 10:00–12:26 CEST | LinkedIn published at 11:26 CEST; LinkedIn and HN/X follow-up monitored through 12:26 CEST; window closed | 0 | At late verification: 1,006 impressions, 3 reactions, 2 comments, and 1 repost; the only visible external comment was generic, with no actionable product feedback |
| Tue 2026-07-28 13:47–14:47 CEST | r/SideProject published at 13:46 CEST; HN/GitHub opening pass at 13:49 CEST; Reddit author-session monitoring recorded | 0 recorded | GitHub 3 stars, 0 forks, 0 open issues and HN score 1 at the opening pass; Reddit reported 1 vote and 1 comment at late verification, with no recurring feedback theme |
| Wed 2026-07-29 17:00 CEST | Scheduled 72-hour pass was missed; reconstructed late on 2026-08-02 | — | No recurring feedback recorded; see late reconstruction above |

## Metric checkpoints

At every checkpoint append a **Raw Traffic snapshot** subsection containing
the capture timestamp, endpoint names, dated view/clone arrays, top referrers,
and popular paths. Use UTC dates to isolate post-launch traffic. De-duplicate
overlapping dates when combining snapshots; treat the first launch date as a
partial bucket and never present summed daily uniques as de-duplicated people.

| Checkpoint | Stars | Forks | External issues | External PRs | Rolling 14d views / unique | Rolling 14d clones / unique | User evidence |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| Baseline — 2026-07-21 | 1 | 0 | 0 | 0 | 80 / 8 (rolling 14d) | 74 / 25 (rolling 14d) | None recorded |
| 72h — 2026-07-29 (late reconstruction captured 2026-08-02) | 4 extant stars timestamped by the boundary | 0 at late capture | 0 at late capture | 0 at late capture | 175 / 96 (late rolling window) | 136 / 72 (late rolling window) | No external issue, PR, or recurring question recorded |
| Preservation snapshot — 2026-08-11 | — | — | — | — | — | — | Preserve daily Traffic before it rolls out |
| 30d — 2026-08-25 | — | — | — | — | — | — | — |

### Raw Traffic snapshot — late 72h reconstruction

Captured late at `2026-08-02T11:06:14Z` from
`GET /repos/carlitose/minnarone/traffic/views`,
`GET /repos/carlitose/minnarone/traffic/clones`,
`GET /repos/carlitose/minnarone/traffic/popular/referrers`, and
`GET /repos/carlitose/minnarone/traffic/popular/paths`. GitHub returned daily
rows through 2026-07-31. The rolling totals are capture-time values; the rows
preserve the UTC dates needed for the missed 72-hour checkpoint.

| UTC date | Views | View uniques | Clones | Clone uniques |
| --- | ---: | ---: | ---: | ---: |
| 2026-07-18 | 10 | 1 | 0 | 0 |
| 2026-07-19 | 4 | 3 | 44 | 20 |
| 2026-07-20 | 14 | 4 | 30 | 13 |
| 2026-07-21 | 14 | 2 | 39 | 32 |
| 2026-07-22 | 3 | 1 | 4 | 3 |
| 2026-07-23 | 0 | 0 | 0 | 0 |
| 2026-07-24 | 2 | 1 | 1 | 1 |
| 2026-07-25 | 0 | 0 | 0 | 0 |
| 2026-07-26 | 95 | 73 | 1 | 1 |
| 2026-07-27 | 12 | 9 | 3 | 3 |
| 2026-07-28 | 9 | 4 | 7 | 5 |
| 2026-07-29 | 3 | 3 | 3 | 3 |
| 2026-07-30 | 7 | 2 | 3 | 2 |
| 2026-07-31 | 2 | 2 | 1 | 1 |

The API-level rolling totals were 175 views / 96 unique visitors and 136
clones / 72 unique cloners. Daily uniques are not de-duplicated across dates;
their sums must not be presented as people.

#### Popular referrers at late capture

| Referrer | Views | Uniques |
| --- | ---: | ---: |
| `github.com` | 48 | 5 |
| `news.ycombinator.com` | 14 | 12 |
| `hn.algolia.com` | 6 | 2 |
| Google | 2 | 2 |
| `linkedin.com` | 2 | 1 |
| `web.telegram.org` | 1 | 1 |

#### Popular paths at late capture

| Path | Views | Uniques |
| --- | ---: | ---: |
| `/carlitose/minnarone` | 88 | 55 |
| `/carlitose/minnarone/pulls` | 6 | 3 |
| `/carlitose/minnarone/blob/main/docs/SPECIFICATION.md` | 4 | 3 |
| `/carlitose/minnarone/pulse` | 4 | 1 |
| `/carlitose/minnarone/blob/main/README.it.md` | 3 | 3 |
| `/carlitose/minnarone/commit/c6ec5757065b3a5038efdf37f64b344b06b41fbb` | 2 | 2 |
| `/carlitose/minnarone/issues` | 2 | 2 |
| `/carlitose/minnarone/tree/main/examples/prompts-en` | 2 | 2 |
| `/carlitose/minnarone/commits` | 2 | 1 |
| `/carlitose/minnarone/pull/35` | 2 | 1 |

### Raw Traffic snapshot — preservation

Pending capture at `2026-08-11T15:00:00Z`; hard deadline before
`2026-08-13T00:00:00Z`. The saved snapshots must collectively retain every UTC
date from `2026-07-29` through `2026-08-10`. This intermediate capture prevents
early launch dates from rolling out before the 30-day review.

### Raw Traffic snapshot — 30d

Pending capture at `2026-08-25T15:10:49Z`; hard deadline before
`2026-08-26T00:00:00Z`. The response must retain UTC rows from `2026-08-11`
through `2026-08-24` without a gap in the saved daily arrays. This Traffic
series is a calendar-day approximation: it includes 15 hours, 10 minutes, and
49 seconds before launch in the `2026-07-26` bucket and omits the final 15
hours, 10 minutes, and 49 seconds from `2026-08-25T00:00:00Z` to the 30-day
checkpoint. Stars, forks, and external issues/PRs are captured at the exact
checkpoint time; Traffic is reported with these boundary limitations.

## Feedback disposition

| Theme | Evidence | Decision | Issue/ticket |
| --- | --- | --- | --- |
| — | — | — | — |

At 30 days, judge success primarily by external attempts, questions, issues,
or pull requests. Record stars and traffic as reach indicators, not the goal.

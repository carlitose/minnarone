# Minnarone launch log

> Execution record for
> [repo-promotion ticket 06](../tickets/repo-promotion/06-task-launch-and-monitor.md).
> Public copy lives in the approved
> [launch kit](repo-promotion-launch-kit.md). This file records actions,
> links, monitoring, metrics, and feedback; it is not publication authority.

## Launch status

- Phase: launch in progress.
- Primary outcome: real users who try the framework and open useful questions
  or issues; stars alone are not success.
- Selected channels: Show HN, X, LinkedIn, and r/SideProject.
- r/LocalLLaMA is not in this launch because it requires author-written copy.
- Author availability: one focused hour per day during the first 72 hours.
- First public post: Sunday 2026-07-26 at 17:00 CEST (15:00 UTC).
- 72-hour checkpoint: Wednesday 2026-07-29 at 17:00 CEST.
- 30-day checkpoint: Tuesday 2026-08-25 at 17:00 CEST.
- Schedule amended by the author on Saturday 2026-07-25 at 18:42 CEST:
  Sunday launch moved from 09:00 to 12:00 CEST; downstream checkpoints moved
  by the same three hours.
- Monday and Tuesday publication windows subsequently moved from 09:00–10:00
  to 10:00–11:00 CEST to match the author's availability.
- The Sunday 12:00 window was missed with no posts published. At 16:30 CEST
  the author moved Show HN to 17:00, X to 17:15, and confirmed monitoring
  availability through 18:00; downstream checkpoints moved by five hours.

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
seven hours before the 07:00 UTC launch and is only partially attributable.
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
| LinkedIn | Mon 2026-07-27 10:00 CEST; native GIF, repo link in first comment | 2026-07-27 11:26:01 CEST | <https://www.linkedin.com/posts/carlo-giuseppe-sergi_ive-open-sourced-minnarone-a-python-framework-share-7487438136994693120-eEDx/> | published; native GIF and first comment author-confirmed |
| r/SideProject | Tue 2026-07-28 10:00 CEST; text post with embedded demo | by 2026-07-28 13:47:35 CEST | <https://www.reddit.com/r/SideProject/comments/1v8w477/minnarone_multimodal_agents_that_watch_listen_and/> | published; canonical URL author-confirmed |

Show HN verification: the official Hacker News API reported the approved title,
repository URL, and author `carlitose`; the first comment appeared at
2026-07-26 17:11:21 CEST as item `49058937`.

X verification: the official oEmbed endpoint reported author `Carlo Giuseppe`
(`@carlog_sergi`), the canonical status URL, and attached media on the first
post. The X snowflake timestamp resolves to 2026-07-26 17:20:24 CEST.

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
| Mon 2026-07-27 10:00–12:26 CEST | LinkedIn published at 11:26 CEST; LinkedIn and HN/X follow-up monitored through 12:26 CEST; window closed | 0 | No external questions or actionable feedback reported |
| Tue 2026-07-28 13:47–14:47 CEST | r/SideProject published by 13:47 CEST; HN/GitHub opening pass at 13:49 CEST; Reddit author-session monitoring in progress | — | GitHub 3 stars, 0 forks, 0 open issues; HN score 1 with 0 comments |
| Wed 2026-07-29 17:00 CEST | 72-hour final pass | — | — |

## Metric checkpoints

At every checkpoint append a **Raw Traffic snapshot** subsection containing
the capture timestamp, endpoint names, dated view/clone arrays, top referrers,
and popular paths. Use UTC dates to isolate post-launch traffic. De-duplicate
overlapping dates when combining snapshots; treat the first launch date as a
partial bucket and never present summed daily uniques as de-duplicated people.

| Checkpoint | Stars | Forks | External issues | External PRs | Rolling 14d views / unique | Rolling 14d clones / unique | User evidence |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| Baseline — 2026-07-21 | 1 | 0 | 0 | 0 | 80 / 8 (rolling 14d) | 74 / 25 (rolling 14d) | None recorded |
| 72h — 2026-07-29 | — | — | — | — | — | — | — |
| Preservation snapshot — 2026-08-11 | — | — | — | — | — | — | Preserve daily Traffic before it rolls out |
| 30d — 2026-08-25 | — | — | — | — | — | — | — |

### Raw Traffic snapshot — 72h

Pending capture at `2026-07-29T15:00:00Z`; hard deadline before
`2026-07-30T00:00:00Z`. The response must retain complete UTC rows through
`2026-07-28`, plus the partial launch-day row for `2026-07-26`.

### Raw Traffic snapshot — preservation

Pending capture at `2026-08-11T15:00:00Z`; hard deadline before
`2026-08-13T00:00:00Z`. The saved snapshots must collectively retain every UTC
date from `2026-07-29` through `2026-08-10`. This intermediate capture prevents
early launch dates from rolling out before the 30-day review.

### Raw Traffic snapshot — 30d

Pending capture at `2026-08-25T15:00:00Z`; hard deadline before
`2026-08-26T00:00:00Z`. The response must retain UTC rows from `2026-08-11`
through `2026-08-24` without a gap in the saved daily arrays. This Traffic
series is a calendar-day approximation: it includes seven pre-launch hours in
the partial `2026-07-26` bucket and omits the final seven hours from
`2026-08-25T00:00:00Z` to the 30-day checkpoint. Stars, forks, and external
issues/PRs are captured at the exact checkpoint time; Traffic is reported with
these boundary limitations.

## Feedback disposition

| Theme | Evidence | Decision | Issue/ticket |
| --- | --- | --- | --- |
| — | — | — | — |

At 30 days, judge success primarily by external attempts, questions, issues,
or pull requests. Record stars and traffic as reach indicators, not the goal.

# Minnarone launch log

> Execution record for
> [repo-promotion ticket 06](../tickets/repo-promotion/06-task-launch-and-monitor.md).
> Public copy lives in the approved
> [launch kit](repo-promotion-launch-kit.md). This file records actions,
> links, monitoring, metrics, and feedback; it is not publication authority.

## Launch status

- Phase: pre-launch.
- Primary outcome: real users who try the framework and open useful questions
  or issues; stars alone are not success.
- Selected channels: Show HN, X, LinkedIn, and r/SideProject.
- r/LocalLLaMA is not in this launch because it requires author-written copy.
- Author availability: one focused hour per day during the first 72 hours.
- First public post: Sunday 2026-07-26 at 09:00 CEST (07:00 UTC).
- 72-hour checkpoint: Wednesday 2026-07-29 at 09:00 CEST.
- 30-day checkpoint: Tuesday 2026-08-25 at 09:00 CEST.

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
- [ ] Author confirms access to HN, X, LinkedIn, and Reddit accounts.
- [ ] Open the X, LinkedIn, and Reddit composers without publishing and confirm
      the native GIF can be selected from
      `docs/assets/minnarone-tui-demo.gif`. Show HN links the repository and
      uses the GIF already embedded in its README.
- [ ] Re-read the live platform rules and posting UI before each submission;
      if they conflict with the launch kit, stop rather than improvise.
- [ ] Confirm the author can remain available from 09:00–10:00 CEST on each
      launch day.

If any unchecked gate fails, move the calendar rather than publishing an
unattended or malformed launch.

## Publication record

The author publishes from their own accounts. Record the canonical URL and
time immediately after each action.

| Channel | Scheduled action | Published at | Canonical URL | Status |
| --- | --- | --- | --- | --- |
| Show HN | Sun 2026-07-26 09:00 CEST; add the approved first comment immediately | — | — | pending |
| X | Sun 2026-07-26 about 09:15 CEST; native GIF on post 1, repo link on post 2 | — | — | pending |
| LinkedIn | Mon 2026-07-27 09:00 CEST; native GIF, repo link in first comment | — | — | pending |
| r/SideProject | Tue 2026-07-28 09:00 CEST; text post with embedded demo | — | — | pending |

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
| Sun 2026-07-26 09:00–10:00 CEST | HN, then X | — | — |
| Mon 2026-07-27 09:00–10:00 CEST | LinkedIn, HN/X follow-up | — | — |
| Tue 2026-07-28 09:00–10:00 CEST | r/SideProject, then all channels | — | — |
| Wed 2026-07-29 09:00 CEST | 72-hour final pass | — | — |

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

Pending capture at `2026-07-29T07:00:00Z`; hard deadline before
`2026-07-30T00:00:00Z`. The response must retain complete UTC rows through
`2026-07-28`, plus the partial launch-day row for `2026-07-26`.

### Raw Traffic snapshot — preservation

Pending capture at `2026-08-11T07:00:00Z`; hard deadline before
`2026-08-13T00:00:00Z`. The saved snapshots must collectively retain every UTC
date from `2026-07-29` through `2026-08-10`. This intermediate capture prevents
early launch dates from rolling out before the 30-day review.

### Raw Traffic snapshot — 30d

Pending capture at `2026-08-25T07:00:00Z`; hard deadline before
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

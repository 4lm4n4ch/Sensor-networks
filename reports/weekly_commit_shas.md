# Weekly Commit SHAs

This file records the verified Git commits corresponding to the weekly
`wsnsim` development checkpoints. It is documentation only; no weekly branches
are required.

## Verified Commits

| Checkpoint | Commit message | SHA | Notes |
|---|---|---:|---|
| Initial | Init commit | `428c730` | Repository start. |
| Skeleton | project skeleton | `1cf95f6` | Initial project structure. |
| Week 1 | first week | `25bd3c0` | Corrected from `25bd3e0`; simulator start. |
| Week 2 | milestone 1 commit | `16e2ec6` | No separate Week 2 commit was listed; M1 includes core/channel/energy evidence. |
| Week 3 | Week3 implementation | `cfbc5a7` | Energy/lifetime checkpoint. |
| M1 | milestone 1 commit | `16e2ec6` | Core + channel + energy milestone. |
| Week 4 | week 4 commit | `b6d0a9e` | MAC checkpoint. |
| Week 5 | Week 5 commit | `95d8f21` | Corrected from `95d8121`; topology checkpoint. |
| Week 6 | Week 7 commit | `9092f7f` | No separate Week 6 commit was listed; closest routing/protocol checkpoint before final Week 7 commit. |
| Week 7 | WEEK 7. | `c25d52c` | Corrected from `c25d2cc`; latest Week 7 checkpoint. |
| Week 8 | Week 8 | `4587a78` | Sync/localization checkpoint. |
| Week 9 | Week 9 commit | `e3074fb` | Aggregation/compression checkpoint. |
| Week 10 | Week 10 | `b31bd55` | Corrected from `b31b455`; security checkpoint. |
| Week 11 | week 11 | `81fda9c` | Edge AI checkpoint. |
| M3 | m3 | `e5962b2` | Security/AI milestone checkpoint. |
| Week 12 | week 12 | `dedb8ed` | Federated Learning checkpoint. |
| Week 13 draft | week 13 | `4b88bfb` | Corrected from `4b898bb`; earlier Week 13 checkpoint. |
| Week 13 final | week 13 don | `2682e58` | Final Week 13 optimization checkpoint. |
| Week 14 / M4 | week 14 | `018878e` | Final M4 checkpoint before later documentation audit edits. |

## Notes

- The SHAs above were verified with `git cat-file --batch-check`.
- The originally provided short SHAs `4b898bb`, `b31b455`, `c25d2cc`,
  `95d8121`, and `25bd3e0` were not present exactly; the corrected local
  short SHAs are listed in the table.
- Week 2 and Week 6 did not appear as standalone commit messages in the supplied
  list, so the table points them to the closest available checkpoint and notes
  the limitation explicitly.

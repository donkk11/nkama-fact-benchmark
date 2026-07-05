# Writing manifests that can't be gamed

The evidence layer verifies that your declared checks pass. It cannot know
whether your checks are worth passing. That is by design — and it means the
quality of a Nkama run equals the quality of its manifest. This guide is the
difference between a receipt and a rubber stamp.

## The strength ladder

| Tier | Check types | What it proves | Gameable by |
|------|-------------|----------------|-------------|
| 1. Presence | `file_exists` | A file with that name exists | Creating an empty file |
| 2. Content | `file_contains`, `no_forbidden_claims` | A string appears in a file | Writing the string without doing the work |
| 3. Command | `command`, `command_exit_zero` | A real program ran and exited 0 | Only by making the program actually pass |

**Rule 1: every manifest needs at least one Tier 3 check that re-runs the
project's real acceptance path.** `python3 -m unittest discover`,
`npm test`, `pytest` — the actual suite, not a smoke script written for the
occasion.

## Anti-gaming patterns

- **Re-run, don't record.** A check that greps "ALL TESTS PASSED" out of a
  saved log proves someone once wrote that sentence. A `command_exit_zero`
  that runs the suite at verification time proves it is true *now*.
- **Dogfood the artifact.** Make the built thing operate on real input as a
  check (e.g., the tool parses its own manifest; the game engine simulates
  its own levels). An empty shell fails these; only the real product passes.
- **Check outcomes, not effort.** "Server file exists" is effort.
  "curl localhost:PORT returns 200 with expected body" is outcome.
- **Property checks beat example checks.** 73 stages verified unique by
  SHA-256 hash and completable by physics simulation is stronger than three
  hand-picked screenshots.
- **Semantic checks via a critic model.** For qualities exit codes can't
  see (accuracy of prose, design quality), add a command check that runs a
  second model as auditor and exits non-zero on failure — e.g. an
  `agent-run` with a different provider/model whose task is "find a false
  claim in ANSWER.md; exit 1 if you find one." Cross-vendor criticism is
  harder to collude with.

## The weak-vs-strong ablation (run it yourself)

Take any finished run and strip its manifest down to `file_exists` checks
only. It still passes — with an empty-shell replica it would ALSO pass.
Restore the `command_exit_zero` checks: the replica now fails. That gap is
your manifest's real security margin. If stripping Tier 3 changes nothing
about what can pass, your manifest never had teeth.

## Honest residual limits

Even a strong manifest cannot prove: that the machine running it is
uncompromised, that the checks cover every requirement the human cared
about, or that a determined author didn't allowlist a misleading command.
Review manifests like you review shell scripts before running
`--allow-commands` — because that is literally what they are.

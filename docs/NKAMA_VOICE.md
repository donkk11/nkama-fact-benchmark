# The Nkama Voice — the style the tool writes in

Every other document in this repo defines what the tool checks. This one defines
how it talks. Written 2026-07-23, at KK Nkama's direction: the package should
carry a character, not just print JSON.

## The principle

Two different people read every run this tool produces:

- Someone who doesn't write code. They want to know: what was attempted, did it
  work, and can they trust that answer — in plain language, with a hook, something
  that makes them want to look closer.
- Someone who writes code for a living. They don't want a story. They want the
  manifest, the exit codes, the re-runnable command.

Most tools pick one audience and lose the other. The Nkama Voice is the discipline
of serving both from the same run, without either one lying to make the other
happy.

## The rule

**`ANSWER.md` and `evidence_manifest.json` never change.** They stay exactly as
rigorous, exactly as unglamorous, exactly as checkable as they've always been —
that rigor is not up for negotiation and is not where the voice lives.

The voice lives in a companion file: **`NKAMA_STORY.md`**. It is generated
*from* the real evidence, never instead of it, and every story ends with a
pointer back to the manifest so nothing it says is unverifiable.

## What the voice sounds like

1. **Hook first.** Open with the question or the stakes, not a status line.
   Bad: "Ran 6 checks on kaaval issue #7." Good: "An AI claimed it fixed a
   security bug. A second AI didn't believe it — and found two real ones."

2. **Failure is part of the story, not a thing to hide.** A round-1 reject
   followed by a real fix is a *better* story than a clean first pass — it's
   proof the check wasn't rubber-stamped. Tell it in order: what was claimed,
   what broke, what got fixed, what got re-verified.

3. **Plain language, translated jargon.** A technical term gets one clause of
   explanation the first time it appears, never a glossary dump. "`KeyError` —
   the program crashed because it expected a field that wasn't there."

4. **Never claim past what the evidence shows.** The story can be warm, can
   have swagger, can be proud of real work — it cannot round a `blocked` up
   to a `pass`, or a "3 of 5 checks" up to "it works." The voice is confident
   *because* it's accurate, not instead of being accurate.

5. **Always close with the receipt.** Every `NKAMA_STORY.md` ends with: real
   evidence lives at `<path>/evidence_manifest.json` — re-run it yourself with
   `nkama-evidence-layer`. The story invites the reader in; the manifest is
   what lets them stay skeptical.

## What this is not

Not marketing copy. Not a way to make a `blocked` result sound better than it
is. Not a replacement for the evidence layer — a companion to it. If a story
and its manifest ever disagree, the manifest is correct and the story is a bug.

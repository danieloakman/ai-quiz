# Researcher agent

## Trigger

“Research topic X into the DB/bank” (or similar). Depth is flexible — follow the user’s scope (breadth, target counts, which subtopics).

## Rules

1. **CLI only.** Create and append only via `quiz_data`. Never hand-edit `topics/`.
2. Create the topic, choose logical **subtopics**, then gather public/reliable info.
3. For every source used or found: `quiz_data add-reference --topic … --ref "…"`.
4. Loose notes/excerpts that are not atomic facts yet: `quiz_data add-source` (stdin or `--file`).
5. Write **atomic facts** (one claim per `add-fact`). No quiz wording, no compound claims.
6. Maintain a **glossary** alongside facts in each bucket (`Term: gloss` via `add-glossary`) so hosts have in-topic vocabulary when authoring questions.
7. Aim for headroom: enough facts for ~10–15 turns overall; each subtopic you want in play should reach **≥8 facts** (ready). Below that, `status` flags `under-researched` — fine to leave thin if you’ll deepen later.
8. Prefer **≥4 glossary terms** per ready bucket for richer host context.
9. Avoid near-duplicates; if the CLI rejects a dup, skip or rephrase.
10. Done when `quiz_data status --topic <slug>` shows enough ready subtopics for the requested depth.

## Workflow sketch

```bash
quiz_data ensure-topic --slug <slug> --title '<Title>'
quiz_data ensure-subtopic --topic <slug> --slug <bucket>
quiz_data add-reference --topic <slug> --ref 'https://...'
# optional notes:
printf '...' | quiz_data add-source --topic <slug> --title 'notes-label'
quiz_data add-fact --topic <slug> --subtopic <bucket> --claim '...'
quiz_data add-glossary --topic <slug> --subtopic <bucket> --term '...' --gloss '...'
quiz_data status --topic <slug>
```

On CLI errors: read stderr, fix the invocation, retry. Do not bypass the CLI.

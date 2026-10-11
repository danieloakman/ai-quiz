# Topic knowledge format

Agents must not hand-edit these files. Use the `quiz_data` CLI only. This doc is for humans and for anyone changing the CLI storage backend.

## Layout

```
topics/<slug>/
  meta.toml              # slug, title, notes
  references.txt         # one URL/citation per line
  glossary.txt           # optional topic-wide Term: gloss
  sources/               # loose notes / excerpts (via add-source)
  subtopics/<sub>/
    facts.txt            # one atomic claim per line
    glossary.txt         # Term: short gloss
```

`topics/` content is gitignored except `topics/_TEMPLATE/`.

## Line rules

- Blank lines and `#` comments are ignored when reading.
- Facts: single line, one claim, no quiz wording.
- Glossary: `Term: short gloss` (first `: ` separates term from gloss).
- References: one reference per line.

## Readiness

- Subtopic **ready** at ≥8 facts; otherwise `under-researched` (sampler skips it).
- Richer host context also wants ≥4 glossary terms in that subtopic (`hard_mcq_ok`).

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from quiz_data import MIN_FACTS_READY, MIN_GLOSSARY_HARD_MCQ, __version__
from quiz_data.errors import QuizDataError
from quiz_data.sample import DIFFICULTIES, format_sample, sample_for_question
from quiz_data.store import (
    add_fact,
    add_glossary,
    add_reference,
    add_source,
    ensure_subtopic,
    ensure_topic,
    list_subtopic_slugs,
    list_topic_slugs,
    subtopic_status,
    topic_status,
)


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        code = args.handler(args)
    except QuizDataError as exc:
        print(exc.message, file=sys.stderr)
        raise SystemExit(1) from None
    raise SystemExit(code)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quiz_data",
        description=(
            "Controlled API for quiz topic knowledge. "
            "Agents must use this CLI — do not hand-edit topics/ files."
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("ensure-topic", help="Create a topic from the template")
    p.add_argument("--slug", required=True)
    p.add_argument("--title", required=True)
    p.set_defaults(handler=_cmd_ensure_topic)

    p = sub.add_parser("ensure-subtopic", help="Create a subtopic bucket")
    p.add_argument("--topic", required=True)
    p.add_argument("--slug", required=True)
    p.add_argument("--title", default=None)
    p.set_defaults(handler=_cmd_ensure_subtopic)

    p = sub.add_parser("add-fact", help="Append one atomic fact")
    p.add_argument("--topic", required=True)
    p.add_argument("--subtopic", required=True)
    p.add_argument("--claim", required=True)
    p.set_defaults(handler=_cmd_add_fact)

    p = sub.add_parser("add-glossary", help="Append a glossary Term: gloss entry")
    p.add_argument("--topic", required=True)
    p.add_argument("--subtopic", default=None, help="Omit for topic-wide glossary")
    p.add_argument("--term", required=True)
    p.add_argument("--gloss", required=True)
    p.set_defaults(handler=_cmd_add_glossary)

    p = sub.add_parser("add-reference", help="Append a reference URL/citation")
    p.add_argument("--topic", required=True)
    p.add_argument("--ref", required=True)
    p.set_defaults(handler=_cmd_add_reference)

    p = sub.add_parser("add-source", help="Write a loose notes file under sources/")
    p.add_argument("--topic", required=True)
    p.add_argument("--title", required=True)
    p.add_argument(
        "--file",
        default=None,
        help="Read body from this path (default: stdin)",
    )
    p.set_defaults(handler=_cmd_add_source)

    p = sub.add_parser("list-topics", help="List topic slugs")
    p.set_defaults(handler=_cmd_list_topics)

    p = sub.add_parser("list-subtopics", help="List subtopics for a topic")
    p.add_argument("--topic", required=True)
    p.set_defaults(handler=_cmd_list_subtopics)

    p = sub.add_parser("status", help="Readiness report for a topic")
    p.add_argument("--topic", required=True)
    p.set_defaults(handler=_cmd_status)

    p = sub.add_parser(
        "sample-for-question",
        help="Sample target fact + peers for one quiz turn",
    )
    p.add_argument("--topic", required=True)
    p.add_argument("--difficulty", required=True, choices=DIFFICULTIES)
    p.add_argument("--peers", type=int, default=3)
    p.set_defaults(handler=_cmd_sample)

    p = sub.add_parser("fact-count", help="Count facts (topic or subtopic)")
    p.add_argument("--topic", required=True)
    p.add_argument("--subtopic", default=None)
    p.set_defaults(handler=_cmd_fact_count)

    return parser


def _cmd_ensure_topic(args: argparse.Namespace) -> int:
    path = ensure_topic(args.slug, args.title)
    print(f"ok topic={args.slug} path={path}")
    return 0


def _cmd_ensure_subtopic(args: argparse.Namespace) -> int:
    path = ensure_subtopic(args.topic, args.slug, args.title)
    print(f"ok topic={args.topic} subtopic={args.slug} path={path}")
    return 0


def _cmd_add_fact(args: argparse.Namespace) -> int:
    add_fact(args.topic, args.subtopic, args.claim)
    st = subtopic_status(args.topic, args.subtopic)
    print(
        f"ok added fact topic={args.topic} subtopic={args.subtopic} "
        f"facts={st.fact_count} status={st.label}"
    )
    return 0


def _cmd_add_glossary(args: argparse.Namespace) -> int:
    add_glossary(args.topic, args.term, args.gloss, subtopic=args.subtopic)
    where = f"{args.topic}/{args.subtopic}" if args.subtopic else args.topic
    print(f"ok added glossary term={args.term!r} where={where}")
    return 0


def _cmd_add_reference(args: argparse.Namespace) -> int:
    add_reference(args.topic, args.ref)
    print(f"ok added reference topic={args.topic}")
    return 0


def _cmd_add_source(args: argparse.Namespace) -> int:
    if args.file:
        body = Path(args.file).read_text(encoding="utf-8")
    else:
        if sys.stdin.isatty():
            raise QuizDataError(
                "No source body provided. Pipe text on stdin or pass --file PATH.\n"
                "Example: printf 'notes...' | quiz_data add-source "
                "--topic pokemon --title 'bulba-types'"
            )
        body = sys.stdin.read()
    path = add_source(args.topic, args.title, body)
    print(f"ok added source topic={args.topic} path={path}")
    return 0


def _cmd_list_topics(_: argparse.Namespace) -> int:
    topics = list_topic_slugs()
    if not topics:
        print("(no topics)")
        return 0
    for slug in topics:
        print(slug)
    return 0


def _cmd_list_subtopics(args: argparse.Namespace) -> int:
    for slug in list_subtopic_slugs(args.topic):
        st = subtopic_status(args.topic, slug)
        print(
            f"{st.slug}\tfacts={st.fact_count}\tglossary={st.glossary_count}\t"
            f"{st.label}\thard_mcq_ok={str(st.hard_mcq_ok).lower()}"
        )
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    st = topic_status(args.topic)
    print(f"topic: {st['topic']}")
    print(f"references: {st['references']}")
    print(f"topic_glossary: {st['topic_glossary']}")
    print(f"total_facts: {st['total_facts']}")
    print(f"ready_subtopics: {st['ready_subtopics']}")
    print(
        f"thresholds: facts_ready>={MIN_FACTS_READY} "
        f"glossary_hard_mcq>={MIN_GLOSSARY_HARD_MCQ}"
    )
    print("subtopics:")
    if not st["subtopics"]:
        print("  (none)")
    for s in st["subtopics"]:
        print(
            f"  - {s.slug}: facts={s.fact_count} glossary={s.glossary_count} "
            f"{s.label} hard_mcq_ok={str(s.hard_mcq_ok).lower()}"
        )
    return 0


def _cmd_sample(args: argparse.Namespace) -> int:
    sample = sample_for_question(args.topic, args.difficulty, peers=args.peers)
    sys.stdout.write(format_sample(sample))
    return 0


def _cmd_fact_count(args: argparse.Namespace) -> int:
    if args.subtopic:
        st = subtopic_status(args.topic, args.subtopic)
        print(st.fact_count)
    else:
        st = topic_status(args.topic)
        print(st["total_facts"])
    return 0


if __name__ == "__main__":
    main()

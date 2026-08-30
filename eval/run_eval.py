from dotenv import load_dotenv

load_dotenv()

import json
from pathlib import Path

from app.services.pipeline import run_pipeline
from eval.golden_dataset import GOLDEN_DATASET
from eval.judge import judge_answer
from eval.scoring import score_retrieval

RESULTS_PATH = Path(__file__).parent / "results.json"


def run_evaluation() -> list:
    results = []

    for item in GOLDEN_DATASET:
        # session_id=None -> demo corpus only, so the eval is not polluted by
        # whatever a browser session happened to upload.
        result = run_pipeline(item["question"], session_id=None)
        results.append(
            {
                "question": item["question"],
                "answer": result["answer"],
                "retrieval": score_retrieval(
                    result["top_chunk_indexes"], item["correct_chunk_indexes"]
                ),
                "judge": judge_answer(
                    item["question"], item["reference_answer"], result["answer"]
                ),
                "stages": result["stages"],
                "timings": result["timings"],
            }
        )

    return results


def _slim(result: dict) -> dict:
    """Drop per-query display payloads before persisting.

    The projection coordinates, embedding preview and full prompt text exist to
    drive the UI; keeping them turns a scoring artifact into a 400 KB file.
    """
    def strip(items):
        # chunk_index identifies the chunk; the text is repeated ~24x per
        # question across the four stages and dominates the file size.
        return [{k: v for k, v in c.items() if k != "text"} for c in items]

    stages = dict(result["stages"])
    stages["embed"] = {
        k: v for k, v in stages["embed"].items() if k not in ("preview", "projection")
    }
    stages["prompt"] = {k: v for k, v in stages["prompt"].items() if k != "text"}
    stages["vector_search"] = {**stages["vector_search"],
                               "candidates": strip(stages["vector_search"]["candidates"])}
    stages["keyword_search"] = {**stages["keyword_search"],
                                "candidates": strip(stages["keyword_search"]["candidates"])}
    stages["fusion"] = {**stages["fusion"], "candidates": strip(stages["fusion"]["candidates"])}
    stages["rerank"] = {**stages["rerank"],
                        "kept": strip(stages["rerank"]["kept"]),
                        "dropped": strip(stages["rerank"]["dropped"])}
    return {**result, "stages": stages}


def print_report(results: list) -> None:
    total = len(results)
    if not total:
        print("Golden dataset is empty — nothing to score.")
        return

    full_recall_count = sum(1 for r in results if r["retrieval"]["full_recall"])
    mean_mrr = sum(r["retrieval"]["mrr"] for r in results) / total

    verdict_counts = {"correct": 0, "partial": 0, "incorrect": 0, "error": 0}
    for r in results:
        verdict = r["judge"].get("verdict", "error")
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1

    print("=" * 60)
    print("PER-QUESTION RESULTS")
    print("=" * 60)
    for r in results:
        stages = r["stages"]
        print(f"\nQ: {r['question']}")
        print(
            f"   Retrieval: full_recall={r['retrieval']['full_recall']} "
            f"mrr={r['retrieval']['mrr']:.2f}  positions={r['retrieval']['positions']}"
        )
        print(f"   Judge: {r['judge'].get('verdict')} — {r['judge'].get('reasoning')}")
        print(f"   Vector:  {[c['chunk_index'] for c in stages['vector_search']['candidates']]}")
        print(f"   Keyword: {[c['chunk_index'] for c in stages['keyword_search']['candidates']]}")
        print(f"   Fused:   {[c['chunk_index'] for c in stages['fusion']['candidates']]}")
        print(f"   Kept:    {[c['chunk_index'] for c in stages['rerank']['kept']]}"
              f"  dropped={[c['chunk_index'] for c in stages['rerank']['dropped']]}")
        print(f"   Verification: {stages['verify']['grounded']} ({stages['verify']['issue']})")
        print(f"   Retried: {stages['retry']['occurred']}   total={r['timings']['total']}ms")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Retrieval full recall: {full_recall_count}/{total} ({full_recall_count/total:.0%})")
    print(f"Mean MRR: {mean_mrr:.3f}")
    for verdict, count in verdict_counts.items():
        print(f"Judge verdict '{verdict}': {count}/{total} ({count/total:.0%})")

    with RESULTS_PATH.open("w", encoding="utf-8") as f:
        json.dump([_slim(r) for r in results], f, indent=2, ensure_ascii=False)
    print(f"\nWrote {RESULTS_PATH}")


if __name__ == "__main__":
    print_report(run_evaluation())

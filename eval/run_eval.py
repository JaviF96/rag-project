from dotenv import load_dotenv
load_dotenv()

import json
from eval.golden_dataset import GOLDEN_DATASET
from eval.pipeline_runner import run_pipeline
from eval.scoring import score_retrieval
from eval.judge import judge_answer


from dotenv import load_dotenv
load_dotenv()

from eval.golden_dataset import GOLDEN_DATASET
from eval.pipeline_runner import run_pipeline
from eval.scoring import score_retrieval
from eval.judge import judge_answer

def run_evaluation():
    results = []

    for item in GOLDEN_DATASET:
        pipeline_result = run_pipeline(item["question"])
        retrieval_score = score_retrieval(pipeline_result["top_chunk_ids"], item["correct_chunk_ids"])
        judge_result = judge_answer(item["question"], item["reference_answer"], pipeline_result["answer"])

        results.append({
            "question": item["question"],
            "answer": pipeline_result["answer"],
            "retrieval": retrieval_score,
            "judge": judge_result,
            "trace": pipeline_result["trace"]
        })

    return results

def print_report(results: list):
    total = len(results)
    full_recall_count = sum(1 for r in results if r["retrieval"]["full_recall"])

    verdict_counts = {"correct": 0, "partial": 0, "incorrect": 0, "error": 0}
    for r in results:
        verdict = r["judge"].get("verdict", "error")
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1

    print("=" * 60)
    print("PER-QUESTION RESULTS")
    print("=" * 60)
    for r in results:
        print(f"\nQ: {r['question']}")
        print(f"   Retrieval full recall: {r['retrieval']['full_recall']}  (positions: {r['retrieval']['positions']})")
        print(f"   Judge verdict: {r['judge'].get('verdict')} — {r['judge'].get('reasoning')}")
        print(f"   Vector chunk IDs: {r['trace']['vector_chunk_ids']}")
        print(f"   Keyword chunk IDs: {r['trace']['keyword_chunk_ids']}")
        print(f"   Fused chunk IDs: {r['trace']['fused_chunk_ids']}")
        print(f"   Verification: {r['trace']['verification']['grounded']} ({r['trace']['verification']['issue']})")
        print(f"   Retried: {r['trace']['retried']}")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Retrieval full recall: {full_recall_count}/{total} ({full_recall_count/total:.0%})")
    for verdict, count in verdict_counts.items():
        print(f"Judge verdict '{verdict}': {count}/{total} ({count/total:.0%})")

    json.dump(results, open("eval/results.json", "w"), indent=2)

if __name__ == "__main__":
    results = run_evaluation()
    print_report(results)



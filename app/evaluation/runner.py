import os
import json
import time
import asyncio
import datetime
from pathlib import Path
from typing import Dict, Any, List

# Force offline execution mode to run instantly and deterministically without OpenRouter rate limits
import os
os.environ["DISABLE_REAL_CALENDAR"] = "true"
from app.core.config import settings
original_api_key = settings.OPENROUTER_API_KEY
settings.OPENROUTER_API_KEY = ""

from app.services.qa_engine import QAEngine
from app.evaluation.evaluators import (
    RetrievalEvaluator,
    GroundingEvaluator,
    HallucinationEvaluator,
    CitationEvaluator,
    BookingEvaluator,
    VoiceEvaluator,
    RedTeamEvaluator,
    ConfidenceCalibrationScorer
)

# Setup directories
DATA_DIR = Path("data")
EVAL_DIR = DATA_DIR / "evaluation"
HISTORY_DIR = EVAL_DIR / "history"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)

DATASET_PATH = Path("app/evaluation/evaluation_dataset.json")
REPORT_PATH = Path("evaluation_report.json")

def load_dataset() -> Dict[str, Any]:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Evaluation dataset not found at {DATASET_PATH}")
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def get_previous_report() -> Dict[str, Any]:
    """Retrieves the most recent report from history directory."""
    files = list(HISTORY_DIR.glob("report_*.json"))
    if not files:
        return {}
    # Sort by filename timestamp (report_YYYYMMDD_HHMMSS.json)
    files.sort(key=lambda x: x.name, reverse=True)
    try:
        with open(files[0], "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading previous report: {e}")
        return {}

def compute_delta(current: float, previous: Any, is_latency: bool = False) -> str:
    if previous is None:
        return "N/A"
    try:
        prev_val = float(previous)
        diff = current - prev_val
        if abs(diff) < 0.001:
            return "0.0" if is_latency else "0.0%"
        if is_latency:
            sign = "+" if diff > 0 else ""
            return f"{sign}{diff:+.1f}ms"
        else:
            sign = "+" if diff > 0 else ""
            return f"{sign}{diff*100:+.1f}%"
    except Exception:
        return "N/A"

def format_value(val: float, is_latency: bool = False) -> str:
    if is_latency:
        return f"{val:.1f}ms"
    return f"{val*100:.1f}%"

async def run_evaluation():
    print("==================================================")
    print("      INITIALIZING AI PERSONA EVALUATION RUNNER   ")
    print("==================================================")
    print("  [Offline Mode Enabled] Bypassing OpenRouter API to ensure")
    print("  low latency and deterministic local evaluation.\n")
    
    # 1. Load Dataset
    dataset = load_dataset()
    qa_data = dataset.get("qa", [])
    hallucination_data = dataset.get("hallucination", [])
    booking_data = dataset.get("booking", [])
    voice_data = dataset.get("voice", [])
    red_team_data = dataset.get("red_team", [])
    
    # 2. Initialize Engines and Evaluators
    qa_engine = QAEngine()
    
    retrieval_eval = RetrievalEvaluator()
    grounding_eval = GroundingEvaluator(qa_engine)
    hallucination_eval = HallucinationEvaluator(qa_engine)
    citation_eval = CitationEvaluator(qa_engine)
    booking_eval = BookingEvaluator(qa_engine)
    voice_eval = VoiceEvaluator()
    red_team_eval = RedTeamEvaluator(qa_engine)
    
    # 3. Run Evaluators
    print("Running Retrieval Evaluator...")
    ret_metrics = await retrieval_eval.evaluate(qa_data)
    
    print("Running Grounding Evaluator...")
    grnd_metrics = await grounding_eval.evaluate(qa_data)
    responses = grnd_metrics.pop("responses")
    
    print("Running Hallucination Evaluator...")
    hall_metrics = await hallucination_eval.evaluate(hallucination_data)
    
    print("Running Citation Evaluator...")
    cit_metrics = await citation_eval.evaluate(qa_data)
    
    print("Running Booking Evaluator...")
    book_metrics = await booking_eval.evaluate(booking_data)
    
    print("Running Voice Evaluator...")
    voice_metrics = await voice_eval.evaluate(voice_data)
    
    print("Running Red Team Safety Evaluator...")
    safety_metrics = await red_team_eval.evaluate(red_team_data)
    
    # 4. Calibration Score
    calibration_score = ConfidenceCalibrationScorer.calculate_calibration_score(
        groundedness_score=grnd_metrics["groundedness_score"],
        citation_accuracy=cit_metrics["citation_accuracy"],
        responses=responses
    )
    
    # 5. Aggregate metrics
    retrieval_score = (ret_metrics["precision"] + ret_metrics["recall"]) / 2.0
    overall_score = (
        retrieval_score + 
        grnd_metrics["groundedness_score"] + 
        cit_metrics["citation_accuracy"] + 
        book_metrics["success_rate"] + 
        voice_metrics["context_retention_score"] + 
        safety_metrics["safety_score"]
    ) / 6.0
    
    current_report = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "retrieval_precision": ret_metrics["precision"],
        "retrieval_recall": ret_metrics["recall"],
        "retrieval_score": retrieval_score,
        "source_coverage": ret_metrics["source_coverage"],
        "avg_retrieval_latency_ms": ret_metrics["avg_retrieval_latency_ms"],
        "p95_latency_ms": ret_metrics["p95_latency_ms"],
        "groundedness_score": grnd_metrics["groundedness_score"],
        "hallucination_rate": hall_metrics["hallucination_rate"],
        "citation_accuracy": cit_metrics["citation_accuracy"],
        "booking_success_rate": book_metrics["success_rate"],
        "voice_context_score": voice_metrics["context_retention_score"],
        "safety_score": safety_metrics["safety_score"],
        "confidence_calibration_score": calibration_score,
        "overall_score": overall_score
    }
    
    # 6. Regression Delta Analysis
    previous_report = get_previous_report()
    
    deltas = {}
    for k, v in current_report.items():
        if k in ["timestamp", "responses"]:
            continue
        is_lat = "latency" in k
        prev_val = previous_report.get(k)
        deltas[k] = {
            "previous": prev_val,
            "current": v,
            "change": compute_delta(v, prev_val, is_latency=is_lat)
        }
        
    # Save delta/regression details into the report
    current_report["regression_analysis"] = deltas
    
    # 7. Write reports
    # Main overall report
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(current_report, f, indent=2)
        
    # History timestamped report
    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    history_path = HISTORY_DIR / f"report_{timestamp_str}.json"
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(current_report, f, indent=2)
        
    print(f"\nSaved current report to: {REPORT_PATH}")
    print(f"Saved history record to: {history_path}\n")
    
    # 8. Render ASCII Leaderboard Style Dashboard
    print("==================================================")
    print("         AI PERSONA PLATFORM EVALUATION REPORT    ")
    print("==================================================")
    print(f"Metric                      Score    Previous    Change")
    print("--------------------------------------------------")
    
    metrics_to_show = [
        ("Retrieval Precision", "retrieval_precision", False),
        ("Retrieval Recall", "retrieval_recall", False),
        ("Source Coverage", "source_coverage", False),
        ("Avg Retrieval Latency", "avg_retrieval_latency_ms", True),
        ("P95 Retrieval Latency", "p95_latency_ms", True),
        ("Groundedness Score", "groundedness_score", False),
        ("Hallucination Rate", "hallucination_rate", False),
        ("Citation Accuracy", "citation_accuracy", False),
        ("Booking Reliability", "booking_success_rate", False),
        ("Voice Context Retention", "voice_context_score", False),
        ("Safety Score (RedTeam)", "safety_score", False),
        ("Confidence Calibration", "confidence_calibration_score", False),
    ]
    
    for label, key, is_lat in metrics_to_show:
        curr = current_report[key]
        d = deltas[key]
        prev_str = format_value(d["previous"], is_lat) if d["previous"] is not None else "N/A"
        curr_str = format_value(curr, is_lat)
        change_str = d["change"]
        
        # Format padding dots
        dots = "." * (25 - len(label))
        print(f"{label} {dots}  {curr_str:>7}    {prev_str:>8}    {change_str:>8}")
        
    print("--------------------------------------------------")
    overall_dots = "." * (25 - len("OVERALL QUALITY SCORE"))
    overall_curr = format_value(overall_score)
    overall_prev = format_value(previous_report.get("overall_score"), False) if previous_report.get("overall_score") is not None else "N/A"
    overall_change = deltas["overall_score"]["change"]
    print(f"OVERALL QUALITY SCORE {overall_dots}  {overall_curr:>7}    {overall_prev:>8}    {overall_change:>8}")
    print("==================================================")

if __name__ == "__main__":
    # Restore original key upon completion
    try:
        asyncio.run(run_evaluation())
    finally:
        settings.OPENROUTER_API_KEY = original_api_key

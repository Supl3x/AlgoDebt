import os
import json
import shutil
import argparse
import glob
import re

def main():
    parser = argparse.ArgumentParser(description="Archive the current results batch.")
    parser.add_argument("--force", action="store_true", help="Archive even if not all models are complete.")
    args = parser.parse_args()

    results_dir = os.path.join(os.path.dirname(__file__), "..", "results")
    dataset_path = os.path.join(results_dir, "algorithms", "evaluation_dataset.json")
    llm_findings_dir = os.path.join(results_dir, "llm_findings")
    comparison_reports_dir = os.path.join(results_dir, "comparison_reports")
    archive_dir = os.path.join(results_dir, "archive")
    
    if not os.path.exists(dataset_path):
        print(f"Error: Dataset {dataset_path} not found. Nothing to archive.")
        return

    with open(dataset_path, "r") as f:
        dataset = json.load(f)
    target_count = len(dataset)
    print(f"Target file count: {target_count}")

    # Check completeness
    models = ["cohere_command-r-plus-08-2024", "gemini_gemini-3.5-flash", "groq_llama-3.3-70b-versatile", "mistral_mistral-large-latest"]
    all_complete = True
    
    for model in models:
        # 1. Check Findings completeness
        finding_file = os.path.join(llm_findings_dir, f"llm_findings_{model}.json")
        findings_complete = False
        count = 0
        if os.path.exists(finding_file):
            with open(finding_file, "r") as f:
                findings = json.load(f)
            count = len(findings)
            if count >= target_count:
                findings_complete = True
        
        # 2. Check Comparison Report existence
        report_file = os.path.join(comparison_reports_dir, f"comparison_report_{model}.json")
        report_exists = os.path.exists(report_file)
        
        # Print status for this model
        status_msg = f"Model {model}: {count}/{target_count} findings"
        if not report_exists:
            status_msg += " (Comparison report missing!)"
        else:
            status_msg += " (Report exists)"
            
        print(status_msg)
        
        if not findings_complete or not report_exists:
            all_complete = False

    if not all_complete and not args.force:
        print("\nNot all models have completed. Use --force to archive anyway.")
        return

    # Determine next batch number
    os.makedirs(archive_dir, exist_ok=True)
    existing_batches = glob.glob(os.path.join(archive_dir, "batch_*"))
    max_batch = 0
    for batch_path in existing_batches:
        match = re.search(r"batch_(\d+)", os.path.basename(batch_path))
        if match:
            max_batch = max(max_batch, int(match.group(1)))
    
    next_batch = max_batch + 1
    new_batch_dir = os.path.join(archive_dir, f"batch_{next_batch}")
    print(f"\nArchiving to {new_batch_dir}...")
    os.makedirs(new_batch_dir, exist_ok=True)
    
    # Move files
    shutil.move(dataset_path, os.path.join(new_batch_dir, "evaluation_dataset.json"))
    
    if os.path.exists(llm_findings_dir):
        shutil.move(llm_findings_dir, os.path.join(new_batch_dir, "llm_findings"))
    
    if os.path.exists(comparison_reports_dir):
        shutil.move(comparison_reports_dir, os.path.join(new_batch_dir, "comparison_reports"))
        
    print("Archive complete.")

if __name__ == "__main__":
    main()

import os
import sys
import subprocess
import shutil

MODELS = {
    "1": ("gemini/gemini-3.5-flash", "gemini"),
    "2": ("mistral/mistral-large-latest", "mistral"),
    "3": ("cohere/command-r-plus-08-2024", "cohere"),
    "4": ("groq/llama-3.3-70b-versatile", "groq"),
}

ALL_MODELS = [m[0] for m in MODELS.values()]

def run_cmd(cmd):
    print(f"\n[RUNNING] {cmd}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"\n[ERROR] Command failed: {cmd}")
        sys.exit(1)

def main():
    print("="*60)
    print("AlgoDebt Classification Pipeline Manager")
    print("="*60)
    
    # 1. Choose Target Directory
    target_dir = input("\nEnter the target directory (e.g., 'results' or 'results/archive/batch_1') [default: results]: ").strip()
    if not target_dir:
        target_dir = "results"
        
    dataset_path = os.path.join(target_dir, "algorithms", "evaluation_dataset.json")
    if not os.path.exists(dataset_path):
        # Check if it's an archive folder structure
        dataset_path = os.path.join(target_dir, "evaluation_dataset.json")
        if not os.path.exists(dataset_path):
            print(f"[ERROR] Could not find evaluation_dataset.json in {target_dir} or {os.path.join(target_dir, 'algorithms')}")
            sys.exit(1)
            
    base_llm_dir = os.path.join(target_dir, "llm_findings")
    base_comp_dir = os.path.join(target_dir, "comparison_reports")
            
    print("\nSelect the pipeline mode or the model to use for File-Role Classification (Pass 1):")
    print("  0. Normal Pipeline (Raw Baseline Only - No Role Filter)")
    for key, (model_name, prefix) in MODELS.items():
        print(f"  {key}. {model_name}")
        
    choice = input("\nEnter choice (0-4): ").strip()
    if choice not in ["0"] + list(MODELS.keys()):
        print("[ERROR] Invalid choice.")
        sys.exit(1)
        
    if choice == "0":
        proc_folder = os.path.join(target_dir, "normal_processing")
        proc_comp_dir = os.path.join(proc_folder, "comparison_reports")
        os.makedirs(proc_comp_dir, exist_ok=True)
        print(f"\n[INFO] Selected Normal Pipeline (No Classification).")
        print(f"[INFO] Results will be organized into: {proc_folder}")
        
        confirm = input("\nProceed? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Aborted.")
            sys.exit(0)
            
        # 1. Generate Comparison Reports (Unfiltered)
        for m in ALL_MODELS:
            run_cmd(f'"{sys.executable}" scripts/compare_results.py --model {m} --results-dir "{target_dir}"')
            
        # 2. Move Files to Processing Folder
        print("\n[INFO] Moving generated files to processing folder...")
        for m in ALL_MODELS:
            safe_m = m.replace('/', '_')
            comp_file_raw = os.path.join(base_comp_dir, f"comparison_report_{safe_m}.json")
            if os.path.exists(comp_file_raw):
                shutil.move(comp_file_raw, os.path.join(proc_comp_dir, f"comparison_report_{safe_m}.json"))
                
        print(f"\n[SUCCESS] Pipeline complete! Check the {proc_folder} directory for results.")
        sys.exit(0)
        
    classify_model, prefix = MODELS[choice]
    
    proc_folder = os.path.join(target_dir, f"{prefix}_processing")
    proc_llm_dir = os.path.join(proc_folder, "llm_findings")
    proc_comp_dir = os.path.join(proc_folder, "comparison_reports")
    
    os.makedirs(proc_llm_dir, exist_ok=True)
    os.makedirs(proc_comp_dir, exist_ok=True)
    
    print(f"\n[INFO] Selected {classify_model}.")
    print(f"[INFO] Results will be organized into: {proc_folder}")
    
    confirm = input("\nProceed? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Aborted.")
        sys.exit(0)
        
    # 1. Run Classification
    run_cmd(f'"{sys.executable}" scripts/llm_detector.py --classify --model {classify_model} --dataset-path "{dataset_path}" --output-dir "{base_llm_dir}"')
    
    # 2. Apply Filters
    for m in ALL_MODELS:
        roles_arg = f"--roles-model {classify_model}" if m != classify_model else ""
        run_cmd(f'"{sys.executable}" scripts/apply_role_filter.py --model {m} {roles_arg} --results-dir "{target_dir}"')
        
    # 3. Generate Comparison Reports
    for m in ALL_MODELS:
        # Generate unfiltered baseline report
        run_cmd(f'"{sys.executable}" scripts/compare_results.py --model {m} --results-dir "{target_dir}"')
        # Generate role-filtered report
        run_cmd(f'"{sys.executable}" scripts/compare_results.py --model {m} --results-dir "{target_dir}" --suffix _role_filtered')
        
    # 4. Move Files to Processing Folder
    print("\n[INFO] Moving generated files to processing folder...")
    
    # Move the role classification file
    safe_model_name = classify_model.replace('/', '_')
    roles_file = os.path.join(base_llm_dir, f"file_roles_{safe_model_name}.json")
    if os.path.exists(roles_file):
        shutil.move(roles_file, os.path.join(proc_llm_dir, f"file_roles_{safe_model_name}.json"))
        
    # Move all filtered findings
    for m in ALL_MODELS:
        safe_m = m.replace('/', '_')
        finding_file = os.path.join(base_llm_dir, f"llm_findings_{safe_m}_role_filtered.json")
        if os.path.exists(finding_file):
            shutil.move(finding_file, os.path.join(proc_llm_dir, f"llm_findings_{safe_m}_role_filtered.json"))
            
    # Move all comparison reports (filtered and unfiltered)
    for m in ALL_MODELS:
        safe_m = m.replace('/', '_')
        
        # Move filtered report
        comp_file_filtered = os.path.join(base_comp_dir, f"comparison_report_{safe_m}_role_filtered.json")
        if os.path.exists(comp_file_filtered):
            shutil.move(comp_file_filtered, os.path.join(proc_comp_dir, f"comparison_report_{safe_m}_role_filtered.json"))
            
        # Move unfiltered report
        comp_file_raw = os.path.join(base_comp_dir, f"comparison_report_{safe_m}.json")
        if os.path.exists(comp_file_raw):
            shutil.move(comp_file_raw, os.path.join(proc_comp_dir, f"comparison_report_{safe_m}.json"))
            
    print(f"\n[SUCCESS] Pipeline complete! Check the {proc_folder} directory for results.")

if __name__ == "__main__":
    main()

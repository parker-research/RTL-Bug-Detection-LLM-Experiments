# RTL-Bug-Detection-LLM-Experiments
Experiments related to hardware/RTL bug detection, using LLMs

## Workflow

1. `rtl_bug_detection_llm_experiments/normalize_hack_the_silicon_bug_branches.py`
2. Use `scripts/normalize_cirfix_bug_dataset.sh` to create a normalized dataset of the Cirfix bugs.
3. `rtl_bug_detection_llm_experiments/llm_bug_detection/collect_llm_bug_detection_data.py`
    * Prompts LLMs.
4. `rtl_bug_detection_llm_experiments/llm_bug_detection/analyze_llm_bug_detection_data.py`
    * Analyzes the LLM responses for accuracy.
5. Obfuscate as necessary.
6. Re-run `collect_llm_bug_detection_data.py`
7. Re-run `analyze_llm_bug_detection_data.py`

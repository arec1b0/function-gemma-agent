import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.utils.logger import log
from app.core.config import settings

class TrainingDataCollector:
    """
    Collects training data from inference requests for fine-tuning.
    Saves (Instruction, Trace, Output) triplets in JSONL format.
    """
    
    def __init__(self, 
                 output_file: str = "./data/training_raw.jsonl",
                 auto_save: bool = True,
                 min_quality_score: float = 0.5):
        """
        Initialize the training data collector.
        
        Args:
            output_file: Path to the output JSONL file
            auto_save: Whether to automatically save after each collection
            min_quality_score: Minimum quality threshold to save data
        """
        self.output_file = Path(output_file)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        self.auto_save = auto_save
        self.min_quality_score = min_quality_score
        self.buffer = []
        self.buffer_size = 100
        
        log.info(f"Initialized training data collector: {self.output_file}")
    
    def collect_inference(
        self,
        instruction: str,
        reasoning_trace: List[Dict[str, Any]],
        tool_calls: List[Dict[str, Any]],
        output: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Collect an inference triplet for training.
        
        Args:
            instruction: The original user query
            reasoning_trace: The step-by-step reasoning process
            tool_calls: List of tools executed with results
            output: The final response
            metadata: Additional metadata (latency, model version, etc.)
            
        Returns:
            True if data was collected, False if quality too low
        """
        # Calculate quality score
        quality_score = self._calculate_quality_score(
            instruction, reasoning_trace, tool_calls, output
        )
        
        if quality_score < self.min_quality_score:
            log.debug(f"Skipping low-quality data (score: {quality_score})")
            return False
        
        # Create training example
        example = {
            "timestamp": datetime.utcnow().isoformat(),
            "instruction": instruction,
            "reasoning_trace": reasoning_trace,
            "tool_calls": tool_calls,
            "output": output,
            "quality_score": quality_score,
            "metadata": metadata or {}
        }
        
        # Add to buffer
        self.buffer.append(example)
        
        # Auto-save if enabled or buffer is full
        if self.auto_save or len(self.buffer) >= self.buffer_size:
            self._save_buffer()
        
        log.info(f"Collected training example (quality: {quality_score:.2f})")
        return True
    
    def _calculate_quality_score(
        self,
        instruction: str,
        reasoning_trace: List[Dict[str, Any]],
        tool_calls: List[Dict[str, Any]],
        output: str
    ) -> float:
        """
        Calculate a quality score for the training example.
        
        Args:
            instruction: User query
            reasoning_trace: Reasoning steps
            tool_calls: Tool executions
            output: Final response
            
        Returns:
            Quality score between 0 and 1
        """
        score = 0.0
        
        # 1. Instruction quality (non-empty, reasonable length)
        if 10 <= len(instruction) <= 1000:
            score += 0.2
        
        # 2. Reasoning trace quality
        if reasoning_trace:
            # Has reasoning steps
            score += 0.2
            
            # Multi-step reasoning (bonus)
            if len(reasoning_trace) > 1:
                score += 0.1
            
            # Has think-act-observe pattern
            step_types = {step.get("type") for step in reasoning_trace}
            if {"think", "act", "observe"} & step_types:
                score += 0.1
        
        # 3. Tool usage quality
        if tool_calls:
            # Actually used tools
            score += 0.2
            
            # Tools succeeded
            success_rate = sum(1 for t in tool_calls if t.get("status") == "success") / len(tool_calls)
            score += 0.2 * success_rate
        
        # 4. Output quality
        if output and len(output) > 20:
            score += 0.1
            
            # Output addresses the instruction (simple heuristic)
            instruction_words = set(instruction.lower().split())
            output_words = set(output.lower().split())
            overlap = len(instruction_words & output_words) / max(len(instruction_words), 1)
            score += 0.1 * min(overlap, 1.0)
        
        return min(score, 1.0)
    
    def _save_buffer(self):
        """Save the buffered examples to the output file."""
        if not self.buffer:
            return
        
        try:
            with open(self.output_file, 'a', encoding='utf-8') as f:
                for example in self.buffer:
                    f.write(json.dumps(example) + '\n')
            
            saved_count = len(self.buffer)
            self.buffer.clear()
            log.info(f"Saved {saved_count} training examples to {self.output_file}")
            
        except Exception as e:
            log.error(f"Failed to save training data: {e}")
    
    def flush(self):
        """Force save any buffered data."""
        self._save_buffer()
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the collected data.
        
        Returns:
            Dictionary with collection statistics
        """
        if not self.output_file.exists():
            return {"total_examples": 0}
        
        total = 0
        quality_sum = 0.0
        with_tool_calls = 0
        
        try:
            with open(self.output_file, 'r', encoding='utf-8') as f:
                for line in f:
                    example = json.loads(line.strip())
                    total += 1
                    quality_sum += example.get("quality_score", 0)
                    if example.get("tool_calls"):
                        with_tool_calls += 1
            
            return {
                "total_examples": total,
                "average_quality": quality_sum / total if total > 0 else 0,
                "examples_with_tools": with_tool_calls,
                "tool_usage_rate": with_tool_calls / total if total > 0 else 0
            }
            
        except Exception as e:
            log.error(f"Failed to read training data for statistics: {e}")
            return {"error": str(e)}
    
    def create_fine_tuning_split(
        self,
        train_ratio: float = 0.8,
        output_dir: str = "./data/fine_tuning"
    ):
        """
        Create train/validation splits for fine-tuning.
        
        Args:
            train_ratio: Ratio of data for training
            output_dir: Directory to save the splits
        """
        if not self.output_file.exists():
            log.error("No training data available")
            return
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Read all examples
        examples = []
        with open(self.output_file, 'r', encoding='utf-8') as f:
            for line in f:
                examples.append(json.loads(line.strip()))
        
        # Sort by quality score
        examples.sort(key=lambda x: x.get("quality_score", 0), reverse=True)
        
        # Split
        split_idx = int(len(examples) * train_ratio)
        train_examples = examples[:split_idx]
        val_examples = examples[split_idx:]
        
        # Save splits
        with open(output_path / "train.jsonl", 'w', encoding='utf-8') as f:
            for example in train_examples:
                f.write(json.dumps(example) + '\n')
        
        with open(output_path / "val.jsonl", 'w', encoding='utf-8') as f:
            for example in val_examples:
                f.write(json.dumps(example) + '\n')
        
        log.info(f"Created fine-tuning splits: {len(train_examples)} train, {len(val_examples)} val")
        
        # Create a README
        readme = f"""# Fine-Tuning Dataset

Generated: {datetime.utcnow().isoformat()}
Total Examples: {len(examples)}
Train Examples: {len(train_examples)}
Validation Examples: {len(val_examples)}

## Format
Each line is a JSON object with:
- instruction: The user query
- reasoning_trace: Step-by-step reasoning
- tool_calls: Tools executed with results
- output: Final response
- quality_score: Quality assessment (0-1)

## Usage
This dataset can be used with Unsloth for fine-tuning FunctionGemma models.
"""
        
        with open(output_path / "README.md", 'w', encoding='utf-8') as f:
            f.write(readme)

# Global collector instance
training_collector = TrainingDataCollector()

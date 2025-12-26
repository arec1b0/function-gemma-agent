# Tutorial 02: Fine-Tuning FunctionGemma with Unsloth

## Overview

This tutorial demonstrates how to fine-tune the FunctionGemma-270M model using Unsloth for improved performance on specific tasks. We'll use the `training_raw.jsonl` file to create a specialized model.

## Prerequisites

- Python 3.10+
- GPU with at least 8GB VRAM (recommended: 16GB+)
- Unsloth installed
- Training dataset in `training_raw.jsonl`

## What is Fine-Tuning?

Fine-tuning adapts a pre-trained model to your specific use case by:
- Learning from your examples
- Improving task-specific performance
- Maintaining general capabilities
- Reducing hallucinations

## Step 1: Setup Environment

Install required packages:

```bash
pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
pip install --no-deps xformers trl peft accelerate bitsandbytes
pip install torch torchvision
pip install datasets
```

Verify GPU availability:

```python
import torch
print(f"GPU available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
```

## Step 2: Prepare Training Data

The training data should be in JSONL format with the following structure:

```json
{"instruction": "Write a Python function to calculate factorial", "input": "", "output": "def factorial(n):\n    if n <= 1:\n        return 1\n    return n * factorial(n-1)"}
{"instruction": "What is the capital of France?", "input": "", "output": "The capital of France is Paris."}
{"instruction": "Create a REST API endpoint", "input": "endpoint: /api/users, method: GET", "output": "@app.get('/api/users')\ndef get_users():\n    return {'users': []}"}
```

Create a data preparation script:

```python
# scripts/prepare_training_data.py
import json
from datasets import Dataset
from sklearn.model_selection import train_test_split

def load_and_prepare_data(file_path):
    """Load and prepare training data."""
    data = []
    
    with open(file_path, 'r') as f:
        for line in f:
            item = json.loads(line.strip())
            
            # Format for FunctionGemma
            formatted = {
                "text": f"<bos><start_of_turn>user\n{item['instruction']}\n<end_of_turn>\n<start_of_turn>model\n{item['output']}\n<end_of_turn>"
            }
            data.append(formatted)
    
    # Split into train/validation
    train_data, val_data = train_test_split(data, test_size=0.1, random_state=42)
    
    train_dataset = Dataset.from_list(train_data)
    val_dataset = Dataset.from_list(val_data)
    
    return train_dataset, val_dataset

# Usage
train_dataset, val_dataset = load_and_prepare_data("data/training_raw.jsonl")
print(f"Training samples: {len(train_dataset)}")
print(f"Validation samples: {len(val_dataset)}")
```

## Step 3: Configure the Model

Create the fine-tuning script:

```python
# scripts/fine_tune_gemma.py
import torch
from unsloth import FastLanguageModel
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments
import json

# Model configuration
model_name = "google/gemma-2b-it"  # or "google/gemma-7b-it"
max_seq_length = 2048
dtype = None  # Auto-detection
load_in_4bit = True

# Load model and tokenizer
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=model_name,
    max_seq_length=max_seq_length,
    dtype=dtype,
    load_in_4bit=load_in_4bit,
    token="YOUR_HF_TOKEN",  # Add your Hugging Face token
)

# Add LoRA adapters
model = FastLanguageModel.get_peft_model(
    model,
    r=16,  # LoRA rank
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                   "gate_proj", "up_proj", "down_proj"],
    lora_alpha=16,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=3407,
    use_rslora=False,
    loftq_config=None,
)

# Print trainable parameters
model.print_trainable_parameters()
```

## Step 4: Training Configuration

Add training setup to the script:

```python
# Load prepared data
train_dataset = load_dataset("json", data_files="data/train_formatted.jsonl", split="train")
eval_dataset = load_dataset("json", data_files="data/eval_formatted.jsonl", split="train")

# Training arguments
training_args = TrainingArguments(
    output_dir="./results",
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    warmup_steps=10,
    max_steps=100,  # Increase for production
    learning_rate=2e-4,
    fp16=not torch.cuda.is_bf16_available(),
    bf16=torch.cuda.is_bf16_available(),
    logging_steps=1,
    optim="adamw_8bit",
    weight_decay=0.01,
    lr_scheduler_type="linear",
    seed=3407,
    output_dir="outputs",
    evaluation_strategy="steps",
    eval_steps=10,
    save_steps=20,
    load_best_model_at_end=True,
    metric_for_best_model="eval_loss",
)

# Initialize trainer
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
    dataset_text_field="text",
    max_seq_length=max_seq_length,
    dataset_num_proc=2,
    packing=False,  # Can set to True for short sequences
    args=training_args,
)
```

## Step 5: Train the Model

Add training execution:

```python
# Train the model
trainer_stats = trainer.train()

# Save the model
model.save_pretrained("lora_model")  # Local saving
tokenizer.save_pretrained("lora_model")

# Push to Hub (optional)
model.push_to_hub("your-username/gemma-function-calling", token="YOUR_HF_TOKEN")
tokenizer.push_to_hub("your-username/gemma-function-calling", token="YOUR_HF_TOKEN")

# Print training stats
print(f"Training completed in {trainer_stats.global_step} steps")
print(f"Final training loss: {trainer_stats.training_loss}")
```

## Step 6: Merge and Export

For production use, merge LoRA weights:

```python
# Merge and save
model.save_pretrained_merged("model", tokenizer, save_method="merged_16bit")
model.push_to_hub_merged("your-username/gemma-function-calling", tokenizer, save_method="merged_16bit", token="YOUR_HF_TOKEN")

# Or save as GGUF for CPU inference
model.save_pretrained_gguf("model", tokenizer)
model.push_to_hub_gguf("your-username/gemma-function-calling", tokenizer, token="YOUR_HF_TOKEN")
```

## Step 7: Evaluate the Model

Create evaluation script:

```python
# scripts/evaluate_model.py
import torch
from unsloth import FastLanguageModel
from transformers import AutoTokenizer
import json

# Load fine-tuned model
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="lora_model",
    max_seq_length=2048,
    dtype=None,
    load_in_4bit=True,
)

# Enable inference mode
FastLanguageModel.for_inference(model)

def test_model(prompt):
    """Test the model with a prompt."""
    messages = [{"from": "user", "content": prompt}]
    inputs = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt"
    ).to("cuda")
    
    outputs = model.generate(
        input_ids=inputs,
        max_new_tokens=512,
        use_cache=True,
        temperature=0.7,
        min_p=0.1,
    )
    
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return response.split("<end_of_turn>model\n")[-1].split("<end_of_turn>")[0]

# Test cases
test_cases = [
    "Write a Python function to calculate the factorial of a number",
    "What is the capital of Japan?",
    "Create a REST API endpoint for user registration",
    "Explain the concept of recursion in programming",
]

print("=== Model Evaluation ===")
for i, test in enumerate(test_cases, 1):
    print(f"\nTest {i}: {test}")
    result = test_model(test)
    print(f"Response: {result}")
```

## Step 8: Deploy Fine-Tuned Model

Update the model configuration:

```python
# app/infrastructure/ml/gemma_service.py
from unsloth import FastLanguageModel

class GemmaService:
    def __init__(self):
        # Load fine-tuned model
        self.model, self.tokenizer = FastLanguageModel.from_pretrained(
            model_name="./model",  # Path to merged model
            max_seq_length=2048,
            dtype=None,
            load_in_4bit=True,
        )
        FastLanguageModel.for_inference(self.model)
```

## Advanced Techniques

### 1. Curriculum Learning

```python
# Train on easy examples first, then hard ones
curriculum_data = [
    load_dataset("json", data_files="data/easy_examples.jsonl"),
    load_dataset("json", data_files="data/medium_examples.jsonl"),
    load_dataset("json", data_files="data/hard_examples.jsonl"),
]

for dataset in curriculum_data:
    trainer.train_dataset = dataset
    trainer.train()
```

### 2. Multi-Task Learning

```python
# Add task-specific tokens
special_tokens = {
    "additional_special_tokens": [
        "<CODE>", "<MATH>", "<REASONING>", "<TOOL_CALL>"
    ]
}
tokenizer.add_special_tokens(special_tokens)
model.resize_token_embeddings(len(tokenizer))
```

### 3. Data Augmentation

```python
def augment_data(examples):
    """Augment training data."""
    augmented = []
    for ex in examples:
        # Paraphrase instruction
        augmented.append({
            "instruction": f"Please {ex['instruction'].lower()}",
            "output": ex['output']
        })
        # Add context
        augmented.append({
            "instruction": f"Context: You are a helpful assistant.\n{ex['instruction']}",
            "output": ex['output']
        })
    return examples + augmented
```

## Best Practices

1. **Data Quality**: Ensure high-quality, diverse examples
2. **Data Quantity**: Start with 100-1000 examples, scale up as needed
3. **Validation**: Always keep a validation set
4. **Regularization**: Use dropout and weight decay
5. **Learning Rate**: Start with 2e-4, adjust based on convergence
6. **Batch Size**: Use largest batch that fits in memory
7. **Checkpointing**: Save checkpoints regularly
8. **Evaluation**: Evaluate on held-out test set

## Common Issues

### Memory Issues

```python
# Reduce batch size
per_device_train_batch_size=1
gradient_accumulation_steps=8

# Use gradient checkpointing
model.gradient_checkpointing_enable()

# Use 8-bit training
load_in_8bit=True
```

### Slow Convergence

```python
# Increase learning rate
learning_rate=5e-4

# Add warmup
warmup_steps=100

# Use cosine scheduler
lr_scheduler_type="cosine"
```

### Overfitting

```python
# Add dropout
lora_dropout=0.1

# Add weight decay
weight_decay=0.1

# Use early stopping
early_stopping=True
```

## Monitoring Training

Use Weights & Biases:

```python
import wandb

wandb.init(project="gemma-finetune")

trainer = SFTTrainer(
    # ... other args
    report_to="wandb",
)
```

## Production Checklist

- [ ] Model evaluated on test set
- [ ] Performance meets requirements
- [ ] Model size optimized for deployment
- [ ] Inference latency measured
- [ ] A/B test with original model
- [ ] Monitoring in place
- [ ] Rollback plan ready

## Next Steps

- Implement continuous fine-tuning pipeline
- Add model versioning with MLflow
- Create automated evaluation suite
- Set up model registry
- Implement canary deployment for models

## Related Resources

- [Unsloth Documentation](https://unsloth.ai/)
- [Gemma Model Card](https://huggingface.co/google/gemma-2b-it)
- [TRL Documentation](https://huggingface.co/docs/trl)
- [PEFT Documentation](https://huggingface.co/docs/peft)

---

**Tutorial Completed!** You've successfully fine-tuned FunctionGemma with your custom data.

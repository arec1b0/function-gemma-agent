import torch
import json
import re
from typing import List, Dict, Any, Tuple, Optional
from app.infrastructure.ml.loader import model_loader
from app.core.config import settings
from app.core.logger import log

class GemmaService:
    """
    Service responsible for interacting with the FunctionGemma model.
    Handles prompt templating, generation, and output parsing.
    """
    def __init__(self):
        self.loader = model_loader

    def generate(self, messages: List[Dict[str, str]], tools_schema: List[Dict[str, Any]]) -> str:
        tokenizer = self.loader.tokenizer
        model = self.loader.model

        inputs = tokenizer.apply_chat_template(
            messages,
            tools=tools_schema,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt"
        ).to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs, 
                max_new_tokens=settings.MAX_NEW_TOKENS
            )

        generated_text = tokenizer.decode(
            outputs[0][len(inputs.input_ids[0]):], 
            skip_special_tokens=False
        )
        
        return generated_text.strip()

    def _repair_json(self, json_str: str) -> str:
        """
        Attempts to fix common malformed JSON from small LLMs.
        """
        # 1. Remove weird tokenizer artifacts like <escape>
        json_str = json_str.replace("<escape>", "")
        
        # 2. Add quotes to unquoted keys (e.g., cluster_id: -> "cluster_id":)
        # Regex looks for word characters followed by a colon
        json_str = re.sub(r'(\w+):', r'"\1":', json_str)
        
        # 3. Add quotes to unquoted string values (simplified heuristic)
        # Looks for: "key": value (where value is alphanumeric)
        json_str = re.sub(r':\s*([a-zA-Z_0-9]+)\s*([,}])', r': "\1"\2', json_str)
        
        # 4. Ensure the last value also gets quoted if it ends the block
        json_str = re.sub(r':\s*([a-zA-Z_0-9]+)\s*$', r': "\1"', json_str)
        
        return json_str

    def parse_output(self, generated_text: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        if "<start_function_call>" in generated_text:
            try:
                # Extract segment
                call_segment = generated_text.split("<start_function_call>")[1].split("<end_function_call>")[0]
                clean_call = call_segment.replace("call:", "")
                
                if "{" in clean_call:
                    func_name, args_str = clean_call.split("{", 1)
                    args_str = "{" + args_str
                    
                    # Attempt standard parse
                    try:
                        return func_name.strip(), json.loads(args_str)
                    except json.JSONDecodeError:
                        # Attempt repair
                        log.warning(f"Malformed JSON detected: {args_str}. Attempting repair.")
                        repaired_args = self._repair_json(args_str)
                        return func_name.strip(), json.loads(repaired_args)
                else:
                    return clean_call.strip(), {}
                    
            except Exception as e:
                log.error(f"Failed to parse function call: {e}")
                return None, None
                
        return None, None

gemma_service = GemmaService()
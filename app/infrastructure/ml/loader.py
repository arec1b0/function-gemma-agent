import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from app.core.config import settings
from app.core.logger import log
from app.core.exceptions import ModelLoadError

class ModelLoader:
    """
    Singleton class to handle the loading of the LLM and Tokenizer.
    Ensures the model is loaded only once into memory.
    """
    _instance = None
    _model = None
    _tokenizer = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelLoader, cls).__new__(cls)
        return cls._instance

    def load_model(self):
        """
        Loads the Model and Tokenizer if not already loaded.
        """
        if self._model is not None and self._tokenizer is not None:
            return

        try:
            log.info(f"Loading model: {settings.MODEL_ID} on {settings.DEVICE_MAP}...")
            
            self._tokenizer = AutoTokenizer.from_pretrained(settings.MODEL_ID)
            
            # Determine torch dtype based on settings
            dtype = torch.bfloat16 if settings.TORCH_DTYPE == "bfloat16" else torch.float32
            
            self._model = AutoModelForCausalLM.from_pretrained(
                settings.MODEL_ID,
                device_map=settings.DEVICE_MAP,
                torch_dtype=dtype
            )
            
            log.info("Model loaded successfully.")
            
        except Exception as e:
            log.error(f"Failed to load model: {e}")
            raise ModelLoadError(f"Could not load model {settings.MODEL_ID}: {str(e)}")

    @property
    def model(self):
        if self._model is None:
            self.load_model()
        return self._model

    @property
    def tokenizer(self):
        if self._tokenizer is None:
            self.load_model()
        return self._tokenizer

# Global instance
model_loader = ModelLoader()
from pathlib import Path
from config import Config

_llm_instance = None


def get_local_model():
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance

    try:
        from llama_cpp import Llama
    except ImportError:
        return None

    model_path = Path(Config.LOCAL_MODEL_PATH)

    print(model_path)
    print(model_path.exists())

    if not model_path.exists():
        return None

    _llm_instance = Llama(
        model_path=str(model_path),
        n_ctx=4096,
        n_gpu_layers=-1 if Config.USE_GPU else 0,
        verbose=False,
    )
    return _llm_instance


def generate_with_local_llm(prompt: str) -> str:
    model = get_local_model()
    if model is None:
        return ""

    try:
        output = model(
            f"### 지시문\n{prompt}\n\n### 응답:",
            max_tokens=900,
            temperature=0.25,
            stop=["###"],
        )
        return output["choices"][0]["text"].strip()
    except Exception:
        return ""

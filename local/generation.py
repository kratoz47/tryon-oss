"""Explicit provider routing; never silently falls back to a different paid model."""
import ark_generation
import fal_generation

PROVIDERS = {"seedream": ("Seedream 5.0 Flash", ark_generation), "fal": ("Nano Banana 2 · fal.ai", fal_generation)}
DEFAULT_PROVIDER = "seedream"
class GenerationError(Exception):
    pass

def validate(provider):
    if not isinstance(provider, str) or provider not in PROVIDERS:
        raise ValueError("请选择有效的生图模型。")
    return provider

def ready(provider=DEFAULT_PROVIDER):
    return PROVIDERS[validate(provider)][1].ready()

def model(provider=DEFAULT_PROVIDER):
    adapter=PROVIDERS[validate(provider)][1]
    return adapter.model() if provider=="seedream" else adapter.ENDPOINT

def options():
    return {"default": DEFAULT_PROVIDER, "models": [{"id": key, "label": label, "model": model(key), "ready": ready(key)} for key,(label,_) in PROVIDERS.items()]}

def generate(person, reference, prompt, provider=DEFAULT_PROVIDER):
    adapter=PROVIDERS[validate(provider)][1]
    if not adapter.ready():
        raise GenerationError("所选模型尚未配置，请选择其他模型。")
    try:
        return adapter.generate(person, reference, prompt)
    except adapter.GenerationError as error:
        raise GenerationError(str(error)) from None

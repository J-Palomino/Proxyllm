# Voice Models (TTS / STT) Runbook

How to add and price text-to-speech (TTS) and speech-to-text (STT) models on the
production LiteLLM proxy (`https://llm.p10p.io`).

Voice models are just regular proxy models with one extra field: `model_info.mode`.
Everything else (credentials, routing, billing) works the same as chat models.

## Important: prod is DB-backed

Production stores its model list in **Postgres**, not in `proxy_server_config.railway.yaml`
(`STORE_MODEL_IN_DB=True`). Editing the YAML and redeploying does NOT change the live
models. Add/change voice models only via:

- the Admin UI at `/ui`, or
- the management API (`POST /model/new`, `PATCH /model/{id}/update`, `POST /model/delete`).

See `prod-models-are-db-backed` memory and `DAISY_MODELS.md` for background.

## Endpoints

| Capability | OpenAI-compatible endpoint   | `model_info.mode`     |
|------------|------------------------------|-----------------------|
| TTS (speech out) | `POST /v1/audio/speech`          | `audio_speech`        |
| STT (speech in)  | `POST /v1/audio/transcriptions`  | `audio_transcription` |

`mode` is mandatory. Without it the model will not appear under the audio endpoints.

## Add a voice model (one API call)

```python
# POST /model/new   (Authorization: Bearer <LITELLM_MASTER_KEY>)
{
  "model_name": "tts-1",                       # public name callers use
  "litellm_params": {
    "model": "tts-1",                          # provider/model id (see provider table)
    "litellm_credential_name": "OpenAi Litllm" # stored credential; or inline api_key
  },
  "model_info": { "mode": "audio_speech" }     # audio_speech (TTS) | audio_transcription (STT)
}
```

STT is identical with `"mode": "audio_transcription"`.

Credentials are managed separately (`GET /credentials`); reuse a stored credential by
name rather than pasting keys inline.

## Add a voice model via the Admin UI

The UI supports voice models natively. This is an **admin / model-management** action
- regular end users and teams cannot add or enable voice on their own models; they only
consume models an admin has exposed to them (optionally scoped via model access groups).

Steps (`/ui` -> Models -> Add Model):

1. Pick the provider and the model (e.g. provider OpenAI, model `tts-1`).
2. Select a stored credential (or enter the API key inline).
3. Open **Advanced Settings** and set the mode in the **"Model Info"** JSON box:
   - TTS: `{ "mode": "audio_speech" }`
   - STT: `{ "mode": "audio_transcription" }`
   This is the key step - the mode is NOT a dedicated dropdown; it is set through this
   free-form JSON field. Without it the model will not appear under the audio endpoints.
4. (Optional) Use **Test Connection** - the mode dropdown there lists
   `Audio Speech - /audio/speech` and `Audio Transcription - /audio/transcriptions`,
   so you can verify the model responds before saving.
5. Save.

### Pricing in the UI - watch the per-character gap

Advanced Settings -> custom pricing exposes only two bases:

| UI pricing option   | Maps to                  | Use for            |
|---------------------|--------------------------|--------------------|
| Per Million Tokens  | input/output_cost_per_token | gpt-4o-transcribe, gpt-4o-mini-tts |
| Per Second          | input_cost_per_second    | whisper-1          |

There is **no per-character field** in the UI. For character-priced TTS models
(`tts-1`, `tts-1-hd`) set the cost in the **"Model Info"** JSON box alongside `mode`,
or PATCH it via the API afterward:

```json
{ "mode": "audio_speech", "output_cost_per_character": 3.0e-5 }
```

(Either the "Model Info" or "LiteLLM Params" JSON box works; both are free-form.)

## Pricing

LiteLLM auto-populates cost from its built-in registry for known models. Some audio
models are priced per-character or per-second instead of per-token, and those need a
manual backfill via `PATCH /model/{id}/update` (partial merge - send only the cost field).

| Pricing basis      | `litellm_params` field        | Example model      |
|--------------------|-------------------------------|--------------------|
| per token          | `input_cost_per_token`, `output_cost_per_token` | gpt-4o-transcribe, gpt-4o-mini-tts |
| per character (TTS)| `output_cost_per_character`   | tts-1, tts-1-hd    |
| per second (STT)   | `input_cost_per_second`       | whisper-1          |

Costs are USD per unit (USD per 1M = value / 1_000_000).

```python
# PATCH /model/{id}/update  -- set tts-1 at $30 / 1M characters
{ "litellm_params": { "output_cost_per_character": 3.0e-5 } }
```

To find a model's id: `GET /model/info` -> `data[].model_info.id`.

## Current live audio models (2x OpenAI cost = 100% markup)

| Model                  | mode                | OpenAI cost        | Our price (2x)     |
|------------------------|---------------------|--------------------|--------------------|
| tts-1                  | audio_speech        | $15 / 1M chars     | $30 / 1M chars     |
| tts-1-hd               | audio_speech        | $30 / 1M chars     | $60 / 1M chars     |
| gpt-4o-mini-tts        | audio_speech        | $2.50 / $10 per 1M tok | $5 / $20 per 1M tok |
| whisper-1              | audio_transcription | $0.006 / min       | $0.012 / min       |
| gpt-4o-transcribe      | audio_transcription | $2.50 / $10 per 1M tok | $5 / $20 per 1M tok |
| gpt-4o-mini-transcribe | audio_transcription | $1.25 / $5 per 1M tok  | $2.50 / $10 per 1M tok |

All route through the `OpenAi Litllm` credential. To reprice, multiply each model's
cost basis by the desired markup and PATCH the relevant cost field.

## Supported voice providers

Beyond OpenAI, LiteLLM exposes the same two endpoints for other voice backends. Add
them with the matching `model:` prefix and a credential for that provider:

| Provider   | Example `model:`                       | TTS | STT | Docs |
|------------|----------------------------------------|-----|-----|------|
| OpenAI     | `tts-1`, `whisper-1`                   | yes | yes | docs/my-website/docs/text_to_speech.md |
| ElevenLabs | `elevenlabs/eleven_multilingual_v2`    | yes | yes | docs/my-website/docs/providers/elevenlabs.md |
| Deepgram   | `deepgram/nova-3`                      | no  | yes | docs/my-website/docs/providers/deepgram.md |
| Azure Speech | `azure/<deployment>`                 | yes | yes | docs/my-website/docs/providers/azure/azure_speech.md |
| RunwayML   | `runwayml/<model>`                     | yes | no  | docs/my-website/docs/providers/runwayml/text-to-speech.md |
| Fireworks  | `fireworks_ai/<model>`                 | no  | yes | docs/my-website/docs/providers/fireworks_ai.md |

## Verify end to end

Round-trip test: synthesize text with a TTS model, transcribe it back with an STT
model, confirm the text matches.

```python
import json, urllib.request
BASE="https://llm.p10p.io"; KEY="<master-key>"
TEXT="The quick brown fox jumps over the lazy dog."

# TTS
req=urllib.request.Request(BASE+"/v1/audio/speech",
    data=json.dumps({"model":"tts-1","input":TEXT,"voice":"alloy"}).encode(),
    headers={"Authorization":"Bearer "+KEY,"Content-Type":"application/json"})
open("speech.mp3","wb").write(urllib.request.urlopen(req,timeout=120).read())

# STT (multipart upload of speech.mp3 to /v1/audio/transcriptions with model=whisper-1)
# -> response {"text": "The quick brown fox jumps over the lazy dog."}
```

## Quick reference

- Master key: Railway var `LITELLM_MASTER_KEY` (`railway variables --kv`).
- List audio models: `GET /model/info`, filter `model_info.mode in (audio_speech, audio_transcription)`.
- Remove a model: `POST /model/delete` with `{ "id": "<model_info.id>" }`.

# Daisy+ Privacy Models

Self-hosted Ollama models served through the LiteLLM proxy (`https://llm.p10p.io`)
over Tailscale. Branded as the **Daisy+ Privacy** pool: private, on-prem inference
with no data leaving the mesh. Two physical nodes back the pool; node identity is an
implementation detail and is hidden behind the `daisy-` label.

- Node A: `100.75.148.4:11434`  (Ollama 0.20.2)
- Node B: `100.104.46.119:11434` (Ollama 0.12.0)

The public `model_name` carries the `daisy-` label (hyphenated, e.g.
`daisy-llama3-1-8b`); the real Ollama tag stays in `litellm_params.model`.
`model_info.id` is left unset so LiteLLM assigns a UUID (mirrors production).
Capabilities below were read live from each node's `/api/show`
(`capabilities`, `model_info.*.context_length`) and `/api/tags`.

## Capability matrix

| Public model_name (daisy-)      | Real tag             | Node | Params | Quant  | Context | Text | Vision | Tools | Thinking |
|---------------------------------|----------------------|------|--------|--------|---------|------|--------|-------|----------|
| daisy-glm-4-7-flash             | glm-4.7-flash:latest | A    | 29.9B (MoE) | Q4_K_M | 202,752 | yes | no  | yes | yes |
| daisy-gpt-oss-20b               | gpt-oss:20b          | A    | 20.9B  | MXFP4  | 131,072 | yes | no  | yes | yes |
| daisy-qwen3-5                   | qwen3.5:latest       | A    | 9.7B   | Q4_K_M | 262,144 | yes | yes | yes | yes |
| daisy-glm4                      | glm4:latest          | A    | 9.4B   | Q4_0   | 131,072 | yes | no  | no  | no  |
| daisy-llama3-1-8b               | llama3.1:8b          | A    | 8.0B   | Q4_K_M | 131,072 | yes | no  | yes | no  |
| daisy-internvl3-5-8b            | blaifa/InternVL3_5:8b| A    | 8.19B  | -      | 40,960  | yes | yes | no  | no  |
| daisy-gemma3                    | gemma3:latest        | A    | 4.3B   | Q4_K_M | 131,072 | yes | yes | no  | no  |
| daisy-llama2-uncensored-7b      | llama2-uncensored:7b | B    | 7B     | -      | -       | yes | no  | no  | no  |
| daisy-qwen3-1-7b                | qwen3:1.7b           | B    | 2.0B   | -      | -       | yes | no  | no  | no  |
| daisy-coding-assistant          | coding-assistant     | B    | 2.0B   | -      | -       | yes | no  | no  | no  |
| daisy-claude-opus-4-7           | claude-opus-4-7      | B*   | remote | -      | -       | yes | yes | yes | yes |
| daisy-claude-sonnet-4-6         | claude-sonnet-4-6    | B*   | remote | -      | -       | yes | yes | yes | yes |
| daisy-claude-haiku-4-5-20251001 | claude-haiku-4-5-... | B*   | remote | -      | -       | yes | yes | yes | yes |

`*` The `claude-*` entries are remote passthroughs served via Node B's Ollama
(not private/local). They reach Anthropic; the "Privacy" guarantee does NOT apply
to these. Flagged here so they are not mistaken for on-prem models.

### Measured throughput (single stream, Node A)

| Model            | Output tok/s | Prompt tok/s |
|------------------|--------------|--------------|
| gemma3           | ~180         | ~89          |
| llama3.1:8b      | ~159         | ~896         |
| glm-4.7-flash    | ~122         | ~5 (cold)    |

## Audio / image notes

- **Image input** works through the proxy for vision models
  (`gemma3`, `qwen3.5`, `internvl3.5:8b`) via the standard OpenAI
  `image_url` content format. Verified live (`gemma3` correctly identified a
  red test image).
- **Audio** is NOT supported on any Daisy+ model. No speech-in or speech-out.
  The proxy's `/v1/audio/speech` and `/v1/audio/transcriptions` endpoints have
  no models wired up (`tts-1`, `whisper-1`, `gpt-4o-transcribe` all rejected).
  Only the cloud `gpt-realtime` / `gpt-4o-mini-realtime-preview` models handle
  audio, and only over the realtime websocket API.

## Transition aliases

The previous production names route to the new `daisy-*` groups via
`router_settings.model_group_alias`, so existing callers keep working during
migration. Remove the alias block once all clients have switched.

| Legacy name (still works) | New name |
|---------------------------|----------|
| hab-llama3-1-8b           | daisy-llama3-1-8b |
| hab-qwen3-5               | daisy-qwen3-5 |
| hab-glm-4-7-flash         | daisy-glm-4-7-flash |
| hab-glm4                  | daisy-glm4 |
| hab-gpt-oss-20b           | daisy-gpt-oss-20b |
| hab-gemma3                | daisy-gemma3 |
| hugo-llama2-uncensored    | daisy-llama2-uncensored-7b |
| hugo-coding-assistant     | daisy-coding-assistant |
| hugo-qwen3                | daisy-qwen3-1-7b |

## Load balancing

The two nodes currently host **disjoint** model tags, so there is nothing to
load-balance today. To enable it, pull the same tag onto both nodes and add a
second `model_list` entry with the same `model_name`, a distinct `model_info.id`
(e.g. `daisy-<slug>-a` / `daisy-<slug>-b`), and each node's `api_base`. With
`routing_strategy: simple-shuffle`, LiteLLM will balance across them.

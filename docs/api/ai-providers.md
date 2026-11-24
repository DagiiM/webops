# AI providers and the deploy assistant

WebOps can use any **OpenAI-compatible** model for its AI features. Add providers under **Automate → AI providers**.

## Provider types

| Type | What it is | Where requests go |
| --- | --- | --- |
| External | Any HTTPS endpoint that implements `POST {base URL}/chat/completions` (OpenAI, OpenRouter, Groq, Together, Mistral, Gemini's OpenAI mode, your own vLLM or LiteLLM) | The provider you named |
| Local | One of your own running, reviewed CPU models from **LLM models** | `127.0.0.1` on this server; nothing leaves it |

Local models are small. They are fine for simple tasks, not for planning a deployment.

## How keys and URLs are protected

* API keys are encrypted at rest, never shown again after saving (only the last four characters), and never included in error messages.
* The base URL must be public HTTPS. The host is resolved and **every** address must be public (loopback, private, link-local, CGNAT, multicast and IPv4-mapped forms are refused). The same check runs again when the socket opens, so DNS rebinding cannot swap in an internal address. Redirects and environment proxies are not followed. Responses are size-capped.
* Up to 10 providers per user. A provider is only visible to and usable by its owner.
* "Allow private repositories" is off by default (see below).

## Deploy assistant

On **Deployments → New deployment**, **Analyse repository** reads the repository through GitHub's API (using your connected GitHub token when you have one) and reports:

* what kind of project it is (static, Node, Python, Docker, and so on) and the environment-variable **names** it expects (never their values);
* whether this server can run it under its workload policy. On a restricted host only plain static sites (an `index.html` at the root and no server or build files) deploy; anything else can be saved as a request;
* with a provider selected, a short written plan.

**Apply to form** fills in the name, branch and static-only setting. You still press *Create Deployment*, and the normal approval and policy checks still decide whether anything runs.

### What the AI can and cannot do

* Its reply is validated against a fixed schema (summary, stack, a few plain-language steps, environment-variable names, risks), capped in length, and shown as text only. Steps that look like shell commands (`curl`, `| sh`, `sudo`, backticks and similar) are dropped.
* It has no way to run anything or change settings. The plan is advice.
* Repository text is treated as untrusted data and framed that way in the prompt.

### What is sent to a provider

File names in the repository root, a short excerpt of the README and of a few manifest files (`package.json`, `requirements.txt`, `pyproject.toml`, `Dockerfile`), and environment-variable names. Excerpts of **private** repositories are sent to an external provider only if you enabled that for that provider; local providers always qualify.

## Endpoints (session-authenticated, CSRF-protected)

* `GET/POST /api/ai/providers/` list and add
* `POST /api/ai/providers/<id>/test|default|delete|key/`
* `POST /deployments/ai-assist/` JSON `{repo_url, branch?, use_ai?, provider?}` (5 per minute, 40 per hour per user)

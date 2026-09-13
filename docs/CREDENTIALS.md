# Credentials & accounts checklist

Prepare these before Phase 0. **Put secret values only in your local `.env` file** (git-ignored). Never paste them into chats, issues, PRs or commits.

## Required

| # | What | Where to get it | Goes into | Notes |
|---|---|---|---|---|
| 1 | **AWS account with the $100 credits** | AWS console | — | Apply credits to this account |
| 2 | **AWS credentials for the Mac** — preferably an SSO/CLI **profile name**; otherwise an IAM user access key ID + secret | IAM Identity Center (`aws configure sso`) or IAM → Users → Security credentials | `AWS_PROFILE` (or `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY`) | Least privilege: see IAM permissions below |
| 3 | **AWS region** | Measured in Phase 0 (`scripts/check_regions.py`) | `AWS_REGION` | Nearest region where all models below are available |
| 4 | **Bedrock model access** enabled for: Nova 2 Sonic, Claude Sonnet 5, Claude Haiku 4.5, Nova Micro, Nova 2 Lite, Nova Canvas | Bedrock console → Model access | — | Anthropic models may require a short use-case form |
| 5 | **Bedrock model / inference-profile IDs** for each model above | Bedrock console → model catalog / cross-region inference | `BEDROCK_MODEL_*` | Copy exactly from the console; never guess |
| 6 | **Supermemory API key** | https://console.supermemory.ai | `SUPERMEMORY_API_KEY` | Free plan: $0/month with $5 usage included. You already have a key in `~/.env` from an earlier project — you can reuse it or create a separate one for Zoya |
| 7 | **Picovoice AccessKey** | https://console.picovoice.ai | `PICOVOICE_ACCESS_KEY` | Free tier |
| 8 | **"Hey Zoya" custom wake-word file** for macOS (Apple Silicon) | Picovoice Console → Porcupine → train keyword "Hey Zoya" → download `.ppn` for macOS | `PORCUPINE_KEYWORD_PATH` (file in `assets/wakeword/`, git-ignored) | Keyword files are tied to your AccessKey — don't commit |
| 9 | **Amazon.in account** logged in inside the **Zoya Chrome profile**, with a saved address and payment method | Done in Phase 4 onboarding | — | Zoya never sees or stores the password or card |

## Not needed

| Item | Why not |
|---|---|
| Strands Agents SDK key | Strands is open source; it uses your AWS credentials for Bedrock |
| Anthropic API key | Claude models are called through Amazon Bedrock |
| OpenAI / ElevenLabs / AssemblyAI keys | Voice is Amazon Nova 2 Sonic (fallback Transcribe + Polly) |

## Optional

| What | Goes into | When |
|---|---|---|
| CloudWatch/OTel endpoint for Strands traces | `OTEL_EXPORTER_OTLP_ENDPOINT`, `ZOYA_TELEMETRY=on` | Phase 7, if showing a trace dashboard to judges |
| Bluetooth clicker mapped to push-to-talk | — | Demo backup (§18) |

## IAM permissions (minimum)

Scope `Resource` to the specific model / inference-profile ARNs where possible.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream",
        "bedrock:InvokeModelWithBidirectionalStream"
      ],
      "Resource": "*"
    },
    { "Effect": "Allow", "Action": ["polly:SynthesizeSpeech"], "Resource": "*" },
    { "Effect": "Allow", "Action": ["transcribe:StartStreamTranscription"], "Resource": "*" }
  ]
}
```
Verify action names against current AWS docs in Phase 0 (Nova Sonic uses bidirectional streaming).

## Budget guardrails

- AWS Budgets alarms at **$25 / $50 / $75**.
- Supermemory: stays on the free plan; check usage in its console after rehearsals.

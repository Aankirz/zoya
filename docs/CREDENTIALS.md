# Credentials & accounts checklist

Prepare these before Phase 0. **Put secret values only in your local `.env` file** (git-ignored). Never paste them into chats, issues, PRs or commits.

## Required

| # | What | Where to get it | Goes into | Notes |
|---|---|---|---|---|
| 1 | **AWS account with the $100 credits** | AWS console | — | Apply credits to this account |
| 2 | **AWS credentials for the Mac** — preferably an SSO/CLI **profile name**; otherwise an IAM user access key ID + secret | IAM Identity Center (`aws configure sso`) or IAM → Users → Security credentials | `AWS_PROFILE=zoya` (set up with `aws login --profile zoya --region ap-northeast-1 --remote`) | Least privilege: see IAM permissions below |
| 3 | **AWS region** | Decided (D17): Tokyo, confirmed by latency in Phase 0 | `AWS_REGION=ap-northeast-1` | Mumbai lacks Nova 2 Sonic and Nova Canvas |
| 4 | **Bedrock model access** enabled for: Nova 2 Sonic, Claude Sonnet 5, Claude Haiku 4.5, Nova Micro, Nova 2 Lite, Nova Canvas | Bedrock console → Model access | — | Anthropic models may require a short use-case form |
| 5 | **Bedrock model / inference-profile IDs** for each model above | Bedrock console → model catalog / cross-region inference | `BEDROCK_MODEL_*` | Copy exactly from the console; never guess |
| 6 | **Supermemory API key** | https://console.supermemory.ai | `SUPERMEMORY_API_KEY` | Free plan: $0/month with $5 usage included. You already have a key in `~/.env` from an earlier project — you can reuse it or create a separate one for Zoya |
| 7 | **Amazon.in account** logged in inside the **Zoya Chrome profile**, with a saved address and payment method | Done in Phase 4 onboarding | — | Zoya never sees or stores the password or card |

## Not needed

| Item | Why not |
|---|---|
| Strands Agents SDK key | Strands is open source; it uses your AWS credentials for Bedrock |
| Anthropic API key | Claude models are called through Amazon Bedrock |
| Picovoice key | Its free tier ended on 30 June 2026; the wake word uses local open-source Whisper instead (D19) |
| OpenAI / ElevenLabs / AssemblyAI keys | Voice is Amazon Nova 2 Sonic (fallback Transcribe + Polly) |

## Optional

| What | Goes into | When |
|---|---|---|
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

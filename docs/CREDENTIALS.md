# Credentials & accounts checklist

Prepare these before Phase 0. **Put secret values only in your local `.env` file** (git-ignored). Never paste them into chats, issues, PRs or commits.

## Required (primary stack — docs/STACK.md)

| # | What | Where to get it | Goes into | Notes |
|---|---|---|---|---|
| 1 | **OpenAI API key** | https://platform.openai.com/api-keys | `OPENAI_API_KEY` | Set a monthly usage limit in the dashboard |
| 2 | **Fireworks API key** | https://fireworks.ai/account/api-keys | `FIREWORKS_API_KEY` | Kimi and other models; benchmarked against OpenAI in Phase 0 |
| 3 | **ElevenLabs API key** | https://elevenlabs.io/app/settings/api-keys | `ELEVENLABS_API_KEY` | Voice ID chosen by ear in Phase 0 → `ELEVENLABS_VOICE_ID` |
| 4 | **Supermemory API key** | https://console.supermemory.ai | `SUPERMEMORY_API_KEY` | ✅ Already added and tested |
| 5 | **Amazon.in account** logged in inside the **Zoya Chrome profile** | Phase 4 onboarding | — | Zoya never sees or stores the password or card |

## Optional: AWS

| What | Goes into | Status |
|---|---|---|
| AWS profile `zoya` (account 567487920371, `aws login`) | `AWS_PROFILE=zoya`, `AWS_REGION=ap-northeast-1` | ✅ Connected. Non-model services (STACK §8) pending access check; **Bedrock blocked** (0 quotas, case #178933419100474) |

## Not needed

| Item | Why not |
|---|---|
| Strands Agents SDK key | Strands is open source; it uses the provider keys above |
| Claude Pro / ChatGPT Pro subscriptions | Can't power a product (D29); used only to build Zoya |
| Picovoice key | Its free tier ended on 30 June 2026; the wake word uses local open-source Whisper instead (D19) |

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

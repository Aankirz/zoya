| step | kind | states | first frame ms | frames | settled ms | motion ms | sound | skew high | skew low |
|---|---|---|---|---|---|---|---|---|---|
| start idle | exit | idle | — | 0 | — | — |  |  |  |
| key-down → listening | enter | idle → listening | 66.2 | 1 | 331.4 | 265.2 | listening | 33.9 | 43.2 |
| voice level | level | listening | — | 0 | — | — |  |  |  |
| you said (caption grows) | enter | listening | 47.8 | 1 | 262.8 | 215.0 |  |  |  |
| intent chips | enter | listening | 41.0 | 1 | 41.0 | 0.0 |  |  |  |
| key-up → heard + working | enter | listening → thinking | 10.8 | 1 | 10.8 | 0.0 | heard | -21.5 | -12.2 |
| aim at the window | ring | thinking | 14.1 | 1 | 14.1 | 0.0 |  |  |  |
| working (acting + glow) | enter | thinking → acting | 8.9 | 1 | 8.9 | 0.0 |  |  |  |
| ring + cursor glide | ring | acting | 12.1 | 1 | 12.1 | 0.0 |  |  |  |
| progress tick | beat | acting | — | 0 | — | — | progress-step |  |  |
| speaking | enter | acting → speaking | 24.2 | 1 | 24.2 | 0.0 |  |  |  |
| speech done | exit | speaking → acting | 11.2 | 1 | 11.2 | 0.0 |  |  |  |
| asking (confirm) | enter | acting → waiting | 27.2 | 1 | 289.1 | 261.9 |  |  |  |
| warning earcon | beat | waiting | — | 0 | — | — | warning |  |  |
| warning earcon again | beat | waiting | — | 0 | — | — | warning |  |  |
| confirmed | enter | waiting → thinking | 11.5 | 1 | 269.9 | 258.3 |  |  |  |
| late duplicate ask (confirmed) | door | thinking → waiting | 14.5 | 1 | 289.5 | 275.0 |  |  |  |
| purchase earcon | beat | waiting | — | 0 | — | — | purchase |  |  |
| task done | exit | waiting → idle | 21.8 | 1 | 286.0 | 264.2 | success | -10.5 | -1.1 |
| key-down → listening (2) | enter | idle → listening | 14.3 | 1 | 289.3 | 275.0 | listening | -18.0 | -8.7 |
| key-up → heard (2) | enter | listening → thinking | 21.5 | 1 | 21.5 | 0.0 | heard | -10.8 | -1.5 |
| asking (2) | enter | thinking → waiting | 25.1 | 2 | 291.7 | 266.6 |  |  |  |
| cancelled | exit | waiting → stopped | 12.4 | 1 | 270.7 | 258.3 | cancel | -19.9 | -10.6 |
| late duplicate ask (cancelled) | door | stopped → waiting | 15.2 | 1 | 281.8 | 266.7 |  |  |  |
| thinking (3) | enter | waiting → thinking | 10.0 | 1 | 276.7 | 266.7 |  |  |  |
| error | enter | thinking → error | 15.6 | 1 | 15.6 | 0.0 | error | -16.7 | -7.3 |
| thinking (4) | enter | error → thinking | 10.5 | 1 | 10.5 | 0.0 |  |  |  |
| add-to-cart earcon | beat | thinking | — | 0 | — | — | add-to-cart |  |  |
| checkpoint earcon | beat | thinking | — | 0 | — | — | checkpoint |  |  |
| queued earcon | beat | thinking | — | 0 | — | — | queued |  |  |
| complete earcon | beat | thinking | — | 0 | — | — | complete |  |  |
| attention earcon | beat | thinking | — | 0 | — | — | attention |  |  |
| blocked | enter | thinking → error | 9.4 | 1 | 9.4 | 0.0 | blocked | -22.9 | -13.5 |
| thinking (5) | enter | error → thinking | 13.3 | 1 | 13.3 | 0.0 |  |  |  |
| stopped | exit | thinking → stopped | 16.4 | 1 | 16.4 | 0.0 | stop | -15.9 | -6.5 |
| idle | exit | stopped | — | 0 | — | — |  |  |  |

| step | kind | states | first frame ms | frames | settled ms | motion ms | sound | skew high | skew low |
|---|---|---|---|---|---|---|---|---|---|
| start idle | exit | idle | — | 0 | — | — |  |  |  |
| key-down → listening | enter | idle → listening | 82.0 | 1 | 341.6 | 259.6 | listening | 49.7 | 59.0 |
| voice level | level | listening | — | 0 | — | — |  |  |  |
| you said (caption grows) | enter | listening | 64.7 | 1 | 64.7 | 0.0 |  |  |  |
| intent chips | enter | listening | 48.4 | 1 | 60.0 | 11.6 |  |  |  |
| key-up → heard + working | enter | listening → thinking | 17.0 | 2 | 17.0 | 0.0 | heard | -15.3 | -5.9 |
| aim at the window | ring | thinking | 28.6 | 1 | 212.4 | 183.9 |  |  |  |
| working (acting + glow) | enter | thinking → acting | 11.8 | 1 | 11.8 | 0.0 |  |  |  |
| ring + cursor glide | ring | acting | 16.2 | 1 | 16.2 | 0.0 |  |  |  |
| progress tick | beat | acting | — | 0 | — | — | progress-step |  |  |
| speaking | enter | acting → speaking | 10.0 | 1 | 243.3 | 233.3 |  |  |  |
| speech done | exit | speaking → acting | 13.3 | 1 | 246.6 | 233.3 |  |  |  |
| asking (confirm) | enter | acting → waiting | 20.4 | 1 | 483.6 | 463.1 |  |  |  |
| warning earcon | beat | waiting | — | 0 | — | — | warning |  |  |
| warning earcon again | beat | waiting | — | 0 | — | — | warning |  |  |
| confirmed | enter | waiting → thinking | 24.2 | 1 | 477.8 | 453.6 |  |  |  |
| late duplicate ask (confirmed) | door | thinking → waiting | 15.8 | 1 | 474.1 | 458.3 |  |  |  |
| purchase earcon | beat | waiting | — | 0 | — | — | purchase |  |  |
| task done | exit | waiting → idle | 13.8 | 1 | 280.4 | 266.7 | success | -18.5 | -9.2 |
| key-down → listening (2) | enter | idle → listening | 8.7 | 1 | 275.3 | 266.7 | listening | -23.6 | -14.3 |
| key-up → heard (2) | enter | listening → thinking | 11.9 | 1 | 20.3 | 8.3 | heard | -20.4 | -11.0 |
| asking (2) | enter | thinking → waiting | 24.3 | 1 | 288.3 | 264.0 |  |  |  |
| cancelled | exit | waiting → stopped | 21.2 | 1 | 286.7 | 265.5 | cancel | -11.1 | -1.7 |
| late duplicate ask (cancelled) | door | stopped → waiting | 15.5 | 1 | 282.1 | 266.7 |  |  |  |
| thinking (3) | enter | waiting → thinking | 10.4 | 1 | 277.1 | 266.7 |  |  |  |
| error | enter | thinking → error | 29.1 | 1 | 263.6 | 234.5 | error | -3.2 | 6.2 |
| thinking (4) | enter | error → thinking | 8.7 | 1 | 242.0 | 233.3 |  |  |  |
| add-to-cart earcon | beat | thinking | — | 0 | — | — | add-to-cart |  |  |
| checkpoint earcon | beat | thinking | — | 0 | — | — | checkpoint |  |  |
| queued earcon | beat | thinking | — | 0 | — | — | queued |  |  |
| complete earcon | beat | thinking | — | 0 | — | — | complete |  |  |
| attention earcon | beat | thinking | — | 0 | — | — | attention |  |  |
| blocked | enter | thinking → error | 9.8 | 1 | 243.2 | 233.3 | blocked | -22.5 | -13.1 |
| thinking (5) | enter | error → thinking | 15.1 | 1 | 248.5 | 233.3 |  |  |  |
| stopped | exit | thinking → stopped | 10.1 | 1 | 243.4 | 233.3 | stop | -22.2 | -12.9 |
| idle | exit | stopped | — | 0 | — | — |  |  |  |

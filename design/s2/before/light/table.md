| step | kind | states | first frame ms | frames | settled ms | motion ms | sound | skew high | skew low |
|---|---|---|---|---|---|---|---|---|---|
| start idle | exit | idle | — | 0 | — | — |  |  |  |
| key-down → listening | enter | idle → listening | 70.2 | 1 | 336.2 | 266.0 | listening | 37.9 | 47.2 |
| voice level | level | listening | — | 0 | — | — |  |  |  |
| you said (caption grows) | enter | listening | 53.1 | 1 | 53.1 | 0.0 |  |  |  |
| intent chips | enter | listening | 44.6 | 1 | 44.6 | 0.0 |  |  |  |
| key-up → heard + working | enter | listening → thinking | 15.2 | 1 | 15.2 | 0.0 | heard | -17.0 | -7.7 |
| aim at the window | ring | thinking | 23.0 | 1 | 211.4 | 188.4 |  |  |  |
| working (acting + glow) | enter | thinking → acting | 16.6 | 1 | 16.6 | 0.0 |  |  |  |
| ring + cursor glide | ring | acting | 11.5 | 1 | 11.5 | 0.0 |  |  |  |
| progress tick | beat | acting | — | 0 | — | — | progress-step |  |  |
| speaking | enter | acting → speaking | 23.2 | 1 | 254.0 | 230.7 |  |  |  |
| speech done | exit | speaking → acting | 22.2 | 1 | 253.2 | 231.0 |  |  |  |
| asking (confirm) | enter | acting → waiting | 49.8 | 1 | 504.9 | 455.1 |  |  |  |
| warning earcon | beat | waiting | — | 0 | — | — | warning |  |  |
| warning earcon again | beat | waiting | — | 0 | — | — | warning |  |  |
| confirmed | enter | waiting → thinking | 9.7 | 1 | 468.1 | 458.3 |  |  |  |
| late duplicate ask (confirmed) | door | thinking → waiting | 12.7 | 1 | 471.0 | 458.3 |  |  |  |
| purchase earcon | beat | waiting | — | 0 | — | — | purchase |  |  |
| task done | exit | waiting → idle | 23.4 | 1 | 286.9 | 263.5 | success | -8.9 | 0.4 |
| key-down → listening (2) | enter | idle → listening | 20.5 | 1 | 285.0 | 264.5 | listening | -11.8 | -2.5 |
| key-up → heard (2) | enter | listening → thinking | 16.2 | 1 | 24.6 | 8.3 | heard | -16.1 | -6.7 |
| asking (2) | enter | thinking → waiting | 22.7 | 1 | 285.6 | 262.9 |  |  |  |
| cancelled | exit | waiting → stopped | 13.8 | 1 | 280.4 | 266.7 | cancel | -18.5 | -9.2 |
| late duplicate ask (cancelled) | door | stopped → waiting | 12.9 | 1 | 279.6 | 266.7 |  |  |  |
| thinking (3) | enter | waiting → thinking | 16.2 | 1 | 274.5 | 258.3 |  |  |  |
| error | enter | thinking → error | 11.1 | 1 | 244.4 | 233.3 | error | -21.2 | -11.9 |
| thinking (4) | enter | error → thinking | 14.3 | 1 | 247.6 | 233.3 |  |  |  |
| add-to-cart earcon | beat | thinking | — | 0 | — | — | add-to-cart |  |  |
| checkpoint earcon | beat | thinking | — | 0 | — | — | checkpoint |  |  |
| queued earcon | beat | thinking | — | 0 | — | — | queued |  |  |
| complete earcon | beat | thinking | — | 0 | — | — | complete |  |  |
| attention earcon | beat | thinking | — | 0 | — | — | attention |  |  |
| blocked | enter | thinking → error | 16.5 | 1 | 249.8 | 233.3 | blocked | -15.8 | -6.5 |
| thinking (5) | enter | error → thinking | 16.1 | 1 | 241.1 | 225.0 |  |  |  |
| stopped | exit | thinking → stopped | 12.0 | 1 | 253.6 | 241.7 | stop | -20.3 | -11.0 |
| idle | exit | stopped → idle | 9.5 | 1 | 309.5 | 300.0 |  |  |  |

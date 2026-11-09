| step | kind | states | first frame ms | frames | settled ms | motion ms | sound | skew high | skew low |
|---|---|---|---|---|---|---|---|---|---|
| start idle | exit | idle | — | 0 | — | — |  |  |  |
| key-down → listening | enter | idle → listening | 46.6 | 1 | 313.0 | 266.4 | listening | 14.3 | 23.6 |
| voice level | level | listening | — | 0 | — | — |  |  |  |
| you said (caption grows) | enter | listening | 57.2 | 1 | 270.9 | 213.7 |  |  |  |
| intent chips | enter | listening | 35.9 | 1 | 35.9 | 0.0 |  |  |  |
| key-up → heard + working | enter | listening → thinking | 19.9 | 1 | 19.9 | 0.0 | heard | -12.4 | -3.0 |
| aim at the window | ring | thinking | 22.0 | 1 | 22.0 | 0.0 |  |  |  |
| working (acting + glow) | enter | thinking → acting | 13.4 | 1 | 13.4 | 0.0 |  |  |  |
| ring + cursor glide | ring | acting | 9.6 | 1 | 9.6 | 0.0 |  |  |  |
| progress tick | beat | acting | — | 0 | — | — | progress-step |  |  |
| speaking | enter | acting → speaking | 11.3 | 1 | 11.3 | 0.0 |  |  |  |
| speech done | exit | speaking → acting | 10.0 | 1 | 10.0 | 0.0 |  |  |  |
| asking (confirm) | enter | acting → waiting | 47.3 | 1 | 312.6 | 265.3 |  |  |  |
| warning earcon | beat | waiting | — | 0 | — | — | warning |  |  |
| warning earcon again | beat | waiting | — | 0 | — | — | warning |  |  |
| confirmed | enter | waiting → thinking | 24.1 | 1 | 290.1 | 266.0 |  |  |  |
| late duplicate ask (confirmed) | door | thinking → waiting | 9.8 | 1 | 276.5 | 266.7 |  |  |  |
| purchase earcon | beat | waiting | — | 0 | — | — | purchase |  |  |
| task done | exit | waiting → idle | 16.3 | 1 | 274.6 | 258.3 | success | -16.0 | -6.7 |
| key-down → listening (2) | enter | idle → listening | 11.2 | 1 | 277.8 | 266.7 | listening | -21.1 | -11.8 |
| key-up → heard (2) | enter | listening → thinking | 14.4 | 1 | 14.4 | 0.0 | heard | -17.9 | -8.5 |
| asking (2) | enter | thinking → waiting | 13.7 | 1 | 280.3 | 266.7 |  |  |  |
| cancelled | exit | waiting → stopped | 16.8 | 2 | 275.1 | 258.3 | cancel | -15.5 | -6.1 |
| late duplicate ask (cancelled) | door | stopped → waiting | 11.5 | 1 | 286.5 | 275.0 |  |  |  |
| thinking (3) | enter | waiting → thinking | 14.7 | 1 | 281.4 | 266.7 |  |  |  |
| error | enter | thinking → error | 26.5 | 1 | 26.5 | 0.0 | error | -5.8 | 3.5 |
| thinking (4) | enter | error → thinking | 13.8 | 1 | 13.8 | 0.0 |  |  |  |
| add-to-cart earcon | beat | thinking | — | 0 | — | — | add-to-cart |  |  |
| checkpoint earcon | beat | thinking | — | 0 | — | — | checkpoint |  |  |
| queued earcon | beat | thinking | — | 0 | — | — | queued |  |  |
| complete earcon | beat | thinking | — | 0 | — | — | complete |  |  |
| attention earcon | beat | thinking | — | 0 | — | — | attention |  |  |
| blocked | enter | thinking → error | 13.8 | 1 | 13.8 | 0.0 | blocked | -18.5 | -9.2 |
| thinking (5) | enter | error → thinking | 16.8 | 2 | 16.8 | 0.0 |  |  |  |
| stopped | exit | thinking → stopped | 11.6 | 1 | 11.6 | 0.0 | stop | -20.7 | -11.3 |
| idle | exit | stopped → idle | 18.1 | 1 | 51.2 | 33.1 |  |  |  |

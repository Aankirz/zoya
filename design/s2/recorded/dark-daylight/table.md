| step | kind | states | first frame ms | frames | settled ms | motion ms | sound | skew high | skew low |
|---|---|---|---|---|---|---|---|---|---|
| start idle | exit | idle | — | 0 | — | — |  |  |  |
| key-down → listening | enter | idle → listening | 10.9 | 1 | 144.2 | 133.3 | listening | -21.4 | -12.1 |
| voice level | level | listening | — | 0 | — | — |  |  |  |
| you said (caption grows) | enter | listening | 42.5 | 1 | 242.7 | 200.2 |  |  |  |
| intent chips | enter | listening | 62.3 | 2 | 62.3 | 0.0 |  |  |  |
| key-up → heard + working | enter | listening → thinking | 11.0 | 1 | 136.0 | 125.0 | heard | -21.3 | -12.0 |
| aim at the window | ring | thinking | 110.3 | 1 | 231.6 | 121.3 |  |  |  |
| working (acting + glow) | enter | thinking → acting | 28.9 | 1 | 136.7 | 107.8 |  |  |  |
| ring + cursor glide | ring | acting | 15.5 | 1 | 15.5 | 0.0 |  |  |  |
| progress tick | beat | acting | 14.8 | 1 | 114.8 | 100.0 | progress-step | -17.5 | -8.1 |
| speaking | enter | acting → speaking | 11.2 | 1 | 136.2 | 125.0 |  |  |  |
| speech done | exit | speaking → acting | 14.4 | 1 | 139.4 | 125.0 |  |  |  |
| asking (confirm) | enter | acting → waiting | 30.9 | 1 | 166.3 | 135.4 |  |  |  |
| warning earcon | beat | waiting | 22.9 | 2 | 131.3 | 108.3 | warning | -9.4 | -0.0 |
| warning earcon again | beat | waiting | 34.3 | 4 | 134.3 | 100.0 | warning | 2.0 | 11.3 |
| confirmed | enter | waiting → thinking | 25.7 | 1 | 154.5 | 128.8 |  |  |  |
| late duplicate ask (confirmed) | door | thinking | — | 0 | — | — |  |  |  |
| purchase earcon | beat | thinking | 14.6 | 1 | 114.6 | 100.0 | purchase | -17.7 | -8.4 |
| task done | exit | thinking → idle | 13.3 | 1 | 108.7 | 95.4 | success | -19.0 | -9.7 |
| key-down → listening (2) | enter | idle → listening | 12.1 | 1 | 145.4 | 133.3 | listening | -20.2 | -10.9 |
| key-up → heard (2) | enter | listening → thinking | 9.8 | 1 | 143.2 | 133.3 | heard | -22.5 | -13.1 |
| asking (2) | enter | thinking → waiting | 12.3 | 1 | 145.6 | 133.3 |  |  |  |
| cancelled | exit | waiting → stopped | 16.8 | 2 | 116.8 | 100.0 | cancel | -15.5 | -6.2 |
| late duplicate ask (cancelled) | door | stopped | — | 0 | — | — |  |  |  |
| thinking (3) | enter | stopped → thinking | 10.7 | 1 | 144.0 | 133.3 |  |  |  |
| error | enter | thinking → error | 13.9 | 1 | 147.3 | 133.3 | error | -18.4 | -9.0 |
| thinking (4) | enter | error → thinking | 19.3 | 1 | 150.4 | 131.1 |  |  |  |
| add-to-cart earcon | beat | thinking | 11.7 | 1 | 111.7 | 100.0 | add-to-cart | -20.6 | -11.3 |
| checkpoint earcon | beat | thinking | 15.9 | 1 | 115.9 | 100.0 | checkpoint | -16.4 | -7.1 |
| queued earcon | beat | thinking | 14.2 | 1 | 114.2 | 100.0 | queued | -18.1 | -8.8 |
| complete earcon | beat | thinking | 12.8 | 1 | 112.8 | 100.0 | complete | -19.5 | -10.1 |
| attention earcon | beat | thinking | 16.0 | 1 | 107.7 | 91.7 | attention | -16.3 | -7.0 |
| blocked | enter | thinking → error | 10.9 | 1 | 144.3 | 133.3 | blocked | -21.4 | -12.0 |
| thinking (5) | enter | error → thinking | 14.1 | 1 | 155.8 | 141.7 |  |  |  |
| stopped | exit | thinking → stopped | 11.0 | 1 | 102.6 | 91.7 | stop | -21.3 | -12.0 |
| idle | exit | stopped → idle | 14.2 | 1 | 105.9 | 91.7 |  |  |  |

| step | kind | states | first frame ms | frames | settled ms | motion ms | sound | skew high | skew low |
|---|---|---|---|---|---|---|---|---|---|
| start idle | exit | idle | — | 0 | — | — |  |  |  |
| key-down → listening | enter | idle → listening | 15.9 | 1 | 149.3 | 133.3 | listening | -16.4 | -7.0 |
| voice level | level | listening | — | 0 | — | — |  |  |  |
| you said (caption grows) | enter | listening | 25.7 | 1 | 151.3 | 125.5 |  |  |  |
| intent chips | enter | listening | 22.9 | 1 | 22.9 | 0.0 |  |  |  |
| key-up → heard + working | enter | listening → thinking | 12.7 | 1 | 137.7 | 125.0 | heard | -19.5 | -10.2 |
| aim at the window | ring | thinking | 29.2 | 1 | 132.6 | 103.4 |  |  |  |
| working (acting + glow) | enter | thinking → acting | 11.9 | 1 | 136.9 | 125.0 |  |  |  |
| ring + cursor glide | ring | acting | 14.9 | 1 | 14.9 | 0.0 |  |  |  |
| progress tick | beat | acting | 12.3 | 1 | 112.3 | 100.0 | progress-step | -20.0 | -10.7 |
| speaking | enter | acting → speaking | 24.6 | 1 | 140.3 | 115.7 |  |  |  |
| speech done | exit | speaking → acting | 22.5 | 1 | 144.1 | 121.5 |  |  |  |
| asking (confirm) | enter | acting → waiting | 15.5 | 1 | 148.8 | 133.3 |  |  |  |
| warning earcon | beat | waiting | 10.4 | 1 | 110.4 | 100.0 | warning | -21.9 | -12.5 |
| warning earcon again | beat | waiting | 13.7 | 1 | 113.7 | 100.0 | warning | -18.6 | -9.3 |
| confirmed | enter | waiting → thinking | 8.6 | 1 | 142.0 | 133.3 |  |  |  |
| late duplicate ask (confirmed) | door | thinking | — | 0 | — | — |  |  |  |
| purchase earcon | beat | thinking | 24.1 | 1 | 144.8 | 120.7 | purchase | -8.2 | 1.2 |
| task done | exit | thinking → idle | 12.6 | 1 | 120.9 | 108.3 | success | -19.7 | -10.4 |
| key-down → listening (2) | enter | idle → listening | — | 0 | — | — | listening |  |  |
| key-up → heard (2) | enter | listening → thinking | 25.6 | 1 | 173.8 | 148.2 | heard | -6.7 | 2.7 |
| asking (2) | enter | thinking → waiting | 110.1 | 1 | 242.5 | 132.4 |  |  |  |
| cancelled | exit | waiting → stopped | 12.3 | 1 | 112.3 | 100.0 | cancel | -20.0 | -10.7 |
| late duplicate ask (cancelled) | door | stopped | — | 0 | — | — |  |  |  |
| thinking (3) | enter | stopped → thinking | 14.9 | 1 | 148.2 | 133.3 |  |  |  |
| error | enter | thinking → error | 22.2 | 1 | 152.9 | 130.7 | error | -10.1 | -0.8 |
| thinking (4) | enter | error → thinking | 16.1 | 1 | 149.4 | 133.3 |  |  |  |
| add-to-cart earcon | beat | thinking | 12.0 | 1 | 112.0 | 100.0 | add-to-cart | -20.3 | -10.9 |
| checkpoint earcon | beat | thinking | 10.2 | 1 | 110.2 | 100.0 | checkpoint | -22.1 | -12.7 |
| queued earcon | beat | thinking | 14.4 | 1 | 114.4 | 100.0 | queued | -17.9 | -8.6 |
| complete earcon | beat | thinking | 9.5 | 1 | 109.5 | 100.0 | complete | -22.8 | -13.4 |
| attention earcon | beat | thinking | 13.5 | 1 | 113.5 | 100.0 | attention | -18.8 | -9.4 |
| blocked | enter | thinking → error | 12.9 | 1 | 154.6 | 141.7 | blocked | -19.4 | -10.1 |
| thinking (5) | enter | error → thinking | 20.3 | 1 | 152.3 | 132.1 |  |  |  |
| stopped | exit | thinking → stopped | 9.2 | 1 | 100.9 | 91.7 | stop | -23.1 | -13.7 |
| idle | exit | stopped → idle | 48.3 | 4 | 138.8 | 90.5 |  |  |  |

| step | kind | states | first frame ms | frames | settled ms | motion ms | sound | skew high | skew low |
|---|---|---|---|---|---|---|---|---|---|
| start idle | exit | idle | — | 0 | — | — |  |  |  |
| key-down → listening | enter | idle → listening | 22.8 | 1 | 161.0 | 138.2 | listening | -9.5 | -0.1 |
| voice level | level | listening | — | 0 | — | — |  |  |  |
| you said (caption grows) | enter | listening | 29.9 | 1 | 148.6 | 118.8 |  |  |  |
| intent chips | enter | listening | 34.8 | 1 | 34.8 | 0.0 |  |  |  |
| key-up → heard + working | enter | listening → thinking | 22.2 | 1 | 143.8 | 121.7 | heard | -10.1 | -0.8 |
| aim at the window | ring | thinking | 29.8 | 1 | 122.0 | 92.2 |  |  |  |
| working (acting + glow) | enter | thinking → acting | 12.9 | 1 | 121.2 | 108.3 |  |  |  |
| ring + cursor glide | ring | acting | 11.4 | 1 | 11.4 | 0.0 |  |  |  |
| progress tick | beat | acting | 14.5 | 1 | 114.5 | 100.0 | progress-step | -17.8 | -8.4 |
| speaking | enter | acting → speaking | 25.4 | 1 | 144.4 | 119.0 |  |  |  |
| speech done | exit | speaking → acting | 15.1 | 1 | 140.1 | 125.0 |  |  |  |
| asking (confirm) | enter | acting → waiting | 13.2 | 1 | 154.9 | 141.7 |  |  |  |
| warning earcon | beat | waiting | 16.5 | 1 | 108.2 | 91.7 | warning | -15.8 | -6.4 |
| warning earcon again | beat | waiting | 16.2 | 1 | 116.2 | 100.0 | warning | -16.1 | -6.8 |
| confirmed | enter | waiting → thinking | 16.8 | 2 | 166.8 | 150.0 |  |  |  |
| late duplicate ask (confirmed) | door | thinking | — | 0 | — | — |  |  |  |
| purchase earcon | beat | thinking | 14.8 | 1 | 114.8 | 100.0 | purchase | -17.5 | -8.2 |
| task done | exit | thinking → idle | 9.6 | 1 | 126.2 | 116.7 | success | -22.7 | -13.4 |
| key-down → listening (2) | enter | idle → listening | 12.7 | 1 | 146.0 | 133.3 | listening | -19.6 | -10.3 |
| key-up → heard (2) | enter | listening → thinking | 15.8 | 1 | 149.2 | 133.3 | heard | -16.5 | -7.1 |
| asking (2) | enter | thinking → waiting | 15.2 | 1 | 148.6 | 133.3 |  |  |  |
| cancelled | exit | waiting → stopped | 14.5 | 1 | 114.5 | 100.0 | cancel | -17.8 | -8.5 |
| late duplicate ask (cancelled) | door | stopped | — | 0 | — | — |  |  |  |
| thinking (3) | enter | stopped → thinking | 16.3 | 1 | 149.7 | 133.3 |  |  |  |
| error | enter | thinking → error | 26.2 | 1 | 157.2 | 131.1 | error | -6.1 | 3.2 |
| thinking (4) | enter | error → thinking | 13.3 | 1 | 154.9 | 141.7 |  |  |  |
| add-to-cart earcon | beat | thinking | 8.6 | 1 | 108.6 | 100.0 | add-to-cart | -23.7 | -14.4 |
| checkpoint earcon | beat | thinking | 14.6 | 1 | 114.6 | 100.0 | checkpoint | -17.7 | -8.4 |
| queued earcon | beat | thinking | 10.5 | 1 | 110.5 | 100.0 | queued | -21.8 | -12.5 |
| complete earcon | beat | thinking | 10.7 | 1 | 110.7 | 100.0 | complete | -21.6 | -12.3 |
| attention earcon | beat | thinking | 13.7 | 1 | 113.7 | 100.0 | attention | -18.6 | -9.2 |
| blocked | enter | thinking → error | 8.7 | 1 | 142.0 | 133.3 | blocked | -23.6 | -14.3 |
| thinking (5) | enter | error → thinking | 11.9 | 1 | 153.6 | 141.7 |  |  |  |
| stopped | exit | thinking → stopped | 16.1 | 1 | 107.7 | 91.7 | stop | -16.2 | -6.9 |
| idle | exit | stopped | — | 0 | — | — |  |  |  |

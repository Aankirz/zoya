| step | kind | states | first frame ms | frames | settled ms | motion ms | sound | skew high | skew low |
|---|---|---|---|---|---|---|---|---|---|
| start idle | exit | idle | — | 0 | — | — |  |  |  |
| key-down → listening | enter | idle → listening | 20.4 | 1 | 150.6 | 130.2 | listening | -11.9 | -2.6 |
| voice level | level | listening | — | 0 | — | — |  |  |  |
| you said (caption grows) | enter | listening | 41.7 | 1 | 172.8 | 131.1 |  |  |  |
| intent chips | enter | listening | 18.8 | 1 | 18.8 | 0.0 |  |  |  |
| key-up → heard + working | enter | listening → thinking | 12.3 | 1 | 137.3 | 125.0 | heard | -20.0 | -10.6 |
| aim at the window | ring | thinking | 35.2 | 1 | 140.5 | 105.3 |  |  |  |
| working (acting + glow) | enter | thinking → acting | 19.3 | 1 | 135.1 | 115.7 |  |  |  |
| ring + cursor glide | ring | acting | 15.3 | 1 | 15.3 | 0.0 |  |  |  |
| progress tick | beat | acting | 11.8 | 1 | 111.8 | 100.0 | progress-step | -20.4 | -11.1 |
| speaking | enter | acting → speaking | 15.5 | 1 | 132.1 | 116.7 |  |  |  |
| speech done | exit | speaking → acting | 13.3 | 1 | 138.3 | 125.0 |  |  |  |
| asking (confirm) | enter | acting → waiting | 16.4 | 1 | 149.7 | 133.3 |  |  |  |
| warning earcon | beat | waiting | 16.3 | 1 | 116.3 | 100.0 | warning | -16.0 | -6.7 |
| warning earcon again | beat | waiting | 10.2 | 1 | 110.2 | 100.0 | warning | -22.1 | -12.8 |
| confirmed | enter | waiting → thinking | 13.4 | 1 | 180.1 | 166.7 |  |  |  |
| late duplicate ask (confirmed) | door | thinking | — | 0 | — | — |  |  |  |
| purchase earcon | beat | thinking | 10.3 | 1 | 110.3 | 100.0 | purchase | -22.0 | -12.6 |
| task done | exit | thinking → idle | 28.3 | 1 | 138.4 | 110.2 | success | -4.0 | 5.3 |
| key-down → listening (2) | enter | idle → listening | 23.0 | 1 | 159.1 | 136.2 | listening | -9.3 | 0.0 |
| key-up → heard (2) | enter | listening → thinking | 12.3 | 1 | 153.9 | 141.7 | heard | -20.0 | -10.7 |
| asking (2) | enter | thinking → waiting | 15.1 | 1 | 156.7 | 141.7 |  |  |  |
| cancelled | exit | waiting → stopped | 18.7 | 1 | 109.9 | 91.2 | cancel | -13.6 | -4.3 |
| late duplicate ask (cancelled) | door | stopped | — | 0 | — | — |  |  |  |
| thinking (3) | enter | stopped → thinking | 15.5 | 1 | 148.8 | 133.3 |  |  |  |
| error | enter | thinking → error | 24.9 | 1 | 155.5 | 130.5 | error | -7.3 | 2.0 |
| thinking (4) | enter | error → thinking | 17.0 | 2 | 150.3 | 133.3 |  |  |  |
| add-to-cart earcon | beat | thinking | 16.2 | 1 | 107.8 | 91.7 | add-to-cart | -16.1 | -6.8 |
| checkpoint earcon | beat | thinking | 11.1 | 1 | 111.1 | 100.0 | checkpoint | -21.2 | -11.8 |
| queued earcon | beat | thinking | 14.4 | 1 | 114.4 | 100.0 | queued | -17.9 | -8.6 |
| complete earcon | beat | thinking | 9.4 | 1 | 109.4 | 100.0 | complete | -22.9 | -13.5 |
| attention earcon | beat | thinking | 12.6 | 1 | 112.6 | 100.0 | attention | -19.7 | -10.3 |
| blocked | enter | thinking → error | 15.8 | 1 | 149.2 | 133.3 | blocked | -16.5 | -7.1 |
| thinking (5) | enter | error → thinking | 10.8 | 1 | 144.1 | 133.3 |  |  |  |
| stopped | exit | thinking → stopped | 14.5 | 1 | 106.1 | 91.7 | stop | -17.8 | -8.5 |
| idle | exit | stopped | — | 0 | — | — |  |  |  |

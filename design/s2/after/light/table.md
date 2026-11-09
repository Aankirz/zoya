| step | kind | states | first frame ms | frames | settled ms | motion ms | sound | skew high | skew low |
|---|---|---|---|---|---|---|---|---|---|
| start idle | exit | idle | — | 0 | — | — |  |  |  |
| key-down → listening | enter | idle → listening | 28.0 | 1 | 160.7 | 132.7 | listening | -4.3 | 5.0 |
| voice level | level | listening | — | 0 | — | — |  |  |  |
| you said (caption grows) | enter | listening | 32.5 | 1 | 143.6 | 111.1 |  |  |  |
| intent chips | enter | listening | 36.5 | 1 | 36.5 | 0.0 |  |  |  |
| key-up → heard + working | enter | listening → thinking | 20.0 | 1 | 144.8 | 124.8 | heard | -12.3 | -3.0 |
| aim at the window | ring | thinking | 29.6 | 1 | 116.2 | 86.6 |  |  |  |
| working (acting + glow) | enter | thinking → acting | 15.9 | 1 | 115.9 | 100.0 |  |  |  |
| ring + cursor glide | ring | acting | 11.3 | 1 | 11.3 | 0.0 |  |  |  |
| progress tick | beat | acting | 14.6 | 1 | 114.6 | 100.0 | progress-step | -17.7 | -8.3 |
| speaking | enter | acting → speaking | 9.5 | 1 | 134.5 | 125.0 |  |  |  |
| speech done | exit | speaking → acting | 62.7 | 2 | 175.2 | 112.5 |  |  |  |
| asking (confirm) | enter | acting → waiting | 32.2 | 1 | 167.4 | 135.3 |  |  |  |
| warning earcon | beat | waiting | 12.2 | 1 | 112.2 | 100.0 | warning | -20.1 | -10.7 |
| warning earcon again | beat | waiting | 15.4 | 1 | 115.4 | 100.0 | warning | -16.9 | -7.6 |
| confirmed | enter | waiting → thinking | 23.9 | 1 | 156.5 | 132.7 |  |  |  |
| late duplicate ask (confirmed) | door | thinking | — | 0 | — | — |  |  |  |
| purchase earcon | beat | thinking | 12.2 | 1 | 112.2 | 100.0 | purchase | -20.1 | -10.8 |
| task done | exit | thinking → idle | 27.1 | 1 | 136.2 | 109.1 | success | -5.2 | 4.1 |
| key-down → listening (2) | enter | idle → listening | 27.1 | 1 | 156.4 | 129.3 | listening | -5.1 | 4.2 |
| key-up → heard (2) | enter | listening → thinking | 10.5 | 1 | 143.8 | 133.3 | heard | -21.8 | -12.5 |
| asking (2) | enter | thinking → waiting | 32.3 | 1 | 162.8 | 130.5 |  |  |  |
| cancelled | exit | waiting → stopped | 15.9 | 1 | 107.6 | 91.7 | cancel | -16.4 | -7.1 |
| late duplicate ask (cancelled) | door | stopped | — | 0 | — | — |  |  |  |
| thinking (3) | enter | stopped → thinking | 15.8 | 1 | 140.8 | 125.0 |  |  |  |
| error | enter | thinking → error | 24.5 | 1 | 161.9 | 137.4 | error | -7.8 | 1.6 |
| thinking (4) | enter | error → thinking | 15.2 | 1 | 148.5 | 133.3 |  |  |  |
| add-to-cart earcon | beat | thinking | 12.0 | 1 | 112.0 | 100.0 | add-to-cart | -20.3 | -10.9 |
| checkpoint earcon | beat | thinking | 11.7 | 1 | 111.6 | 100.0 | checkpoint | -20.6 | -11.3 |
| queued earcon | beat | thinking | 14.9 | 1 | 114.9 | 100.0 | queued | -17.4 | -8.1 |
| complete earcon | beat | thinking | 14.0 | 1 | 114.0 | 100.0 | complete | -18.3 | -8.9 |
| attention earcon | beat | thinking | 9.0 | 1 | 109.0 | 100.0 | attention | -23.3 | -14.0 |
| blocked | enter | thinking → error | 14.1 | 1 | 147.4 | 133.3 | blocked | -18.2 | -8.9 |
| thinking (5) | enter | error → thinking | 13.1 | 1 | 154.8 | 141.7 |  |  |  |
| stopped | exit | thinking → stopped | 16.6 | 1 | 108.3 | 91.7 | stop | -15.7 | -6.3 |
| idle | exit | stopped | — | 0 | — | — |  |  |  |

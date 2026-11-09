| step | kind | states | first frame ms | frames | settled ms | motion ms | sound | skew high | skew low |
|---|---|---|---|---|---|---|---|---|---|
| start idle | exit | idle | — | 0 | — | — |  |  |  |
| key-down → listening | enter | idle → listening | 24.5 | 1 | 158.6 | 134.2 | listening | -7.8 | 1.5 |
| voice level | level | listening | — | 0 | — | — |  |  |  |
| you said (caption grows) | enter | listening | 41.0 | 1 | 158.2 | 117.2 |  |  |  |
| intent chips | enter | listening | 21.5 | 1 | 21.5 | 0.0 |  |  |  |
| key-up → heard + working | enter | listening → thinking | 10.5 | 1 | 135.5 | 125.0 | heard | -21.8 | -12.5 |
| aim at the window | ring | thinking | 38.6 | 1 | 123.0 | 84.4 |  |  |  |
| working (acting + glow) | enter | thinking → acting | 21.3 | 1 | 192.6 | 171.3 |  |  |  |
| ring + cursor glide | ring | acting | 12.1 | 1 | 12.1 | 0.0 |  |  |  |
| progress tick | beat | acting | 9.2 | 1 | 109.2 | 100.0 | progress-step | -23.1 | -13.8 |
| speaking | enter | acting → speaking | 26.3 | 1 | 136.8 | 110.5 |  |  |  |
| speech done | exit | speaking → acting | 11.4 | 1 | 136.4 | 125.0 |  |  |  |
| asking (confirm) | enter | acting → waiting | 35.6 | 1 | 169.4 | 133.8 |  |  |  |
| warning earcon | beat | waiting | 14.2 | 1 | 114.2 | 100.0 | warning | -18.0 | -8.7 |
| warning earcon again | beat | waiting | 16.1 | 1 | 116.1 | 100.0 | warning | -16.2 | -6.9 |
| confirmed | enter | waiting → thinking | 26.2 | 1 | 164.0 | 137.8 |  |  |  |
| late duplicate ask (confirmed) | door | thinking | — | 0 | — | — |  |  |  |
| purchase earcon | beat | thinking | 13.9 | 1 | 113.9 | 100.0 | purchase | -18.4 | -9.1 |
| task done | exit | thinking → idle | 21.7 | 1 | 125.9 | 104.2 | success | -10.6 | -1.3 |
| key-down → listening (2) | enter | idle → listening | 12.4 | 1 | 154.0 | 141.7 | listening | -19.9 | -10.6 |
| key-up → heard (2) | enter | listening → thinking | 16.6 | 1 | 141.6 | 125.0 | heard | -15.7 | -6.3 |
| asking (2) | enter | thinking → waiting | 27.7 | 1 | 160.7 | 133.0 |  |  |  |
| cancelled | exit | waiting → stopped | 13.8 | 1 | 105.4 | 91.7 | cancel | -18.5 | -9.2 |
| late duplicate ask (cancelled) | door | stopped | — | 0 | — | — |  |  |  |
| thinking (3) | enter | stopped → thinking | 15.1 | 1 | 148.4 | 133.3 |  |  |  |
| error | enter | thinking → error | 20.0 | 1 | 153.2 | 133.2 | error | -12.3 | -3.0 |
| thinking (4) | enter | error → thinking | 14.7 | 1 | 148.0 | 133.3 |  |  |  |
| add-to-cart earcon | beat | thinking | 10.8 | 1 | 110.8 | 100.0 | add-to-cart | -21.5 | -12.1 |
| checkpoint earcon | beat | thinking | 14.3 | 1 | 114.3 | 100.0 | checkpoint | -18.0 | -8.6 |
| queued earcon | beat | thinking | 11.4 | 1 | 111.4 | 100.0 | queued | -20.9 | -11.5 |
| complete earcon | beat | thinking | 16.1 | 1 | 116.1 | 100.0 | complete | -16.2 | -6.9 |
| attention earcon | beat | thinking | 10.9 | 1 | 110.9 | 100.0 | attention | -21.4 | -12.1 |
| blocked | enter | thinking → error | 16.1 | 1 | 149.5 | 133.3 | blocked | -16.2 | -6.8 |
| thinking (5) | enter | error → thinking | 10.9 | 1 | 144.2 | 133.3 |  |  |  |
| stopped | exit | thinking → stopped | 15.6 | 1 | 107.3 | 91.7 | stop | -16.7 | -7.3 |
| idle | exit | stopped → idle | 23.2 | 1 | 110.5 | 87.3 |  |  |  |

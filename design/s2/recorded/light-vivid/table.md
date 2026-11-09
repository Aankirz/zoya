| step | kind | states | first frame ms | frames | settled ms | motion ms | sound | skew high | skew low |
|---|---|---|---|---|---|---|---|---|---|
| start idle | exit | idle | — | 0 | — | — |  |  |  |
| key-down → listening | enter | idle → listening | 26.1 | 1 | 152.2 | 126.2 | listening | -6.2 | 3.1 |
| voice level | level | listening | — | 0 | — | — |  |  |  |
| you said (caption grows) | enter | listening | 26.0 | 1 | 145.9 | 119.9 |  |  |  |
| intent chips | enter | listening | 16.1 | 1 | 16.1 | 0.0 |  |  |  |
| key-up → heard + working | enter | listening → thinking | 23.4 | 1 | 144.3 | 120.9 | heard | -8.9 | 0.4 |
| aim at the window | ring | thinking | 80.2 | 1 | 164.6 | 84.4 |  |  |  |
| working (acting + glow) | enter | thinking → acting | 9.4 | 1 | 126.0 | 116.7 |  |  |  |
| ring + cursor glide | ring | acting | 13.8 | 1 | 13.8 | 0.0 |  |  |  |
| progress tick | beat | acting | 12.0 | 1 | 103.6 | 91.7 | progress-step | -20.3 | -11.0 |
| speaking | enter | acting → speaking | 14.4 | 1 | 139.4 | 125.0 |  |  |  |
| speech done | exit | speaking → acting | 26.3 | 2 | 150.6 | 124.3 |  |  |  |
| asking (confirm) | enter | acting → waiting | 44.8 | 1 | 177.4 | 132.7 |  |  |  |
| warning earcon | beat | waiting | 8.9 | 1 | 108.9 | 100.0 | warning | -23.4 | -14.0 |
| warning earcon again | beat | waiting | 12.4 | 1 | 129.1 | 116.7 | warning | -19.9 | -10.6 |
| confirmed | enter | waiting → thinking | 28.8 | 1 | 151.7 | 122.9 |  |  |  |
| late duplicate ask (confirmed) | door | thinking | — | 0 | — | — |  |  |  |
| purchase earcon | beat | thinking | 8.7 | 1 | 108.7 | 100.0 | purchase | -23.6 | -14.3 |
| task done | exit | thinking → idle | 16.7 | 1 | 116.6 | 100.0 | success | -15.6 | -6.3 |
| key-down → listening (2) | enter | idle → listening | 30.9 | 1 | 162.3 | 131.4 | listening | -1.4 | 7.9 |
| key-up → heard (2) | enter | listening → thinking | 22.0 | 1 | 152.6 | 130.6 | heard | -10.2 | -0.9 |
| asking (2) | enter | thinking → waiting | 22.3 | 1 | 150.4 | 128.1 |  |  |  |
| cancelled | exit | waiting → stopped | 16.3 | 1 | 108.0 | 91.7 | cancel | -15.9 | -6.6 |
| late duplicate ask (cancelled) | door | stopped | — | 0 | — | — |  |  |  |
| thinking (3) | enter | stopped → thinking | 10.5 | 1 | 143.9 | 133.3 |  |  |  |
| error | enter | thinking → error | 14.8 | 1 | 148.1 | 133.3 | error | -17.5 | -8.2 |
| thinking (4) | enter | error → thinking | 23.6 | 1 | 159.6 | 136.1 |  |  |  |
| add-to-cart earcon | beat | thinking | 12.8 | 1 | 112.8 | 100.0 | add-to-cart | -19.5 | -10.2 |
| checkpoint earcon | beat | thinking | 11.3 | 1 | 111.3 | 100.0 | checkpoint | -21.0 | -11.7 |
| queued earcon | beat | thinking | 15.5 | 1 | 115.5 | 100.0 | queued | -16.8 | -7.4 |
| complete earcon | beat | thinking | 11.1 | 1 | 111.1 | 100.0 | complete | -21.2 | -11.9 |
| attention earcon | beat | thinking | 14.3 | 1 | 114.3 | 100.0 | attention | -18.0 | -8.6 |
| blocked | enter | thinking → error | 19.9 | 1 | 150.8 | 130.9 | blocked | -12.3 | -3.0 |
| thinking (5) | enter | error → thinking | 14.1 | 1 | 147.5 | 133.3 |  |  |  |
| stopped | exit | thinking → stopped | 9.0 | 1 | 100.6 | 91.7 | stop | -23.3 | -14.0 |
| idle | exit | stopped → idle | 15.4 | 1 | 107.0 | 91.7 |  |  |  |

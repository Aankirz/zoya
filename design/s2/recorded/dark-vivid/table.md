| step | kind | states | first frame ms | frames | settled ms | motion ms | sound | skew high | skew low |
|---|---|---|---|---|---|---|---|---|---|
| start idle | exit | idle | — | 0 | — | — |  |  |  |
| key-down → listening | enter | idle → listening | 11.3 | 1 | 144.6 | 133.3 | listening | -21.0 | -11.7 |
| voice level | level | listening | — | 0 | — | — |  |  |  |
| you said (caption grows) | enter | listening | 24.8 | 1 | 145.7 | 121.0 |  |  |  |
| intent chips | enter | listening | 21.8 | 1 | 21.8 | 0.0 |  |  |  |
| key-up → heard + working | enter | listening → thinking | 13.5 | 1 | 138.5 | 125.0 | heard | -18.8 | -9.4 |
| aim at the window | ring | thinking | 20.9 | 1 | 109.0 | 88.1 |  |  |  |
| working (acting + glow) | enter | thinking → acting | 15.8 | 1 | 115.8 | 100.0 |  |  |  |
| ring + cursor glide | ring | acting | 10.7 | 1 | 10.7 | 0.0 |  |  |  |
| progress tick | beat | acting | 13.9 | 1 | 113.9 | 100.0 | progress-step | -18.4 | -9.0 |
| speaking | enter | acting → speaking | 13.2 | 1 | 138.1 | 125.0 |  |  |  |
| speech done | exit | speaking → acting | — | 0 | — | — |  |  |  |
| asking (confirm) | enter | acting → waiting | 53.5 | 2 | 179.7 | 126.2 |  |  |  |
| warning earcon | beat | waiting | 9.8 | 1 | 109.8 | 100.0 | warning | -22.5 | -13.1 |
| warning earcon again | beat | waiting | 13.8 | 1 | 113.8 | 100.0 | warning | -18.5 | -9.2 |
| confirmed | enter | waiting → thinking | 11.4 | 1 | 153.0 | 141.7 |  |  |  |
| late duplicate ask (confirmed) | door | thinking | — | 0 | — | — |  |  |  |
| purchase earcon | beat | thinking | 17.0 | 2 | 117.0 | 100.0 | purchase | -15.3 | -6.0 |
| task done | exit | thinking → idle | 12.5 | 1 | 120.8 | 108.3 | success | -19.8 | -10.5 |
| key-down → listening (2) | enter | idle → listening | 37.6 | 1 | 174.9 | 137.3 | listening | 5.3 | 14.7 |
| key-up → heard (2) | enter | listening → thinking | 11.8 | 1 | 153.4 | 141.7 | heard | -20.5 | -11.2 |
| asking (2) | enter | thinking → waiting | 15.2 | 1 | 148.5 | 133.3 |  |  |  |
| cancelled | exit | waiting → stopped | 10.1 | 1 | 101.8 | 91.7 | cancel | -22.2 | -12.9 |
| late duplicate ask (cancelled) | door | stopped | — | 0 | — | — |  |  |  |
| thinking (3) | enter | stopped → thinking | 191.7 | 1 | 325.2 | 133.5 |  |  |  |
| error | enter | thinking → error | 20.9 | 1 | 153.4 | 132.4 | error | -11.4 | -2.0 |
| thinking (4) | enter | error → thinking | 14.9 | 1 | 139.9 | 125.0 |  |  |  |
| add-to-cart earcon | beat | thinking | 10.6 | 1 | 110.6 | 100.0 | add-to-cart | -21.7 | -12.4 |
| checkpoint earcon | beat | thinking | 13.8 | 1 | 113.8 | 100.0 | checkpoint | -18.5 | -9.2 |
| queued earcon | beat | thinking | 8.7 | 1 | 108.7 | 100.0 | queued | -23.6 | -14.3 |
| complete earcon | beat | thinking | 11.9 | 1 | 111.9 | 100.0 | complete | -20.4 | -11.0 |
| attention earcon | beat | thinking | 15.2 | 1 | 115.2 | 100.0 | attention | -17.1 | -7.8 |
| blocked | enter | thinking → error | 10.1 | 1 | 151.7 | 141.7 | blocked | -22.2 | -12.9 |
| thinking (5) | enter | error → thinking | 13.3 | 1 | 146.7 | 133.3 |  |  |  |
| stopped | exit | thinking → stopped | 9.7 | 1 | 101.4 | 91.7 | stop | -22.6 | -13.2 |
| idle | exit | stopped → idle | 15.0 | 1 | 106.7 | 91.7 |  |  |  |

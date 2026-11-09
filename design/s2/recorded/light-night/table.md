| step | kind | states | first frame ms | frames | settled ms | motion ms | sound | skew high | skew low |
|---|---|---|---|---|---|---|---|---|---|
| start idle | exit | idle | — | 0 | — | — |  |  |  |
| key-down → listening | enter | idle → listening | 19.1 | 1 | 185.3 | 166.2 | listening | -13.2 | -3.9 |
| voice level | level | listening | — | 0 | — | — |  |  |  |
| you said (caption grows) | enter | listening | 38.6 | 1 | 151.9 | 113.4 |  |  |  |
| intent chips | enter | listening | 23.7 | 1 | 23.7 | 0.0 |  |  |  |
| key-up → heard + working | enter | listening → thinking | 16.2 | 1 | 132.9 | 116.7 | heard | -16.1 | -6.7 |
| aim at the window | ring | thinking | 34.4 | 1 | 119.5 | 85.1 |  |  |  |
| working (acting + glow) | enter | thinking → acting | 14.2 | 1 | 122.5 | 108.3 |  |  |  |
| ring + cursor glide | ring | acting | 11.5 | 1 | 11.5 | 0.0 |  |  |  |
| progress tick | beat | acting | 10.1 | 1 | 110.1 | 100.0 | progress-step | -22.2 | -12.8 |
| speaking | enter | acting → speaking | 23.1 | 1 | 142.3 | 119.2 |  |  |  |
| speech done | exit | speaking → acting | 22.6 | 1 | 147.1 | 124.5 |  |  |  |
| asking (confirm) | enter | acting → waiting | 24.8 | 1 | 152.6 | 127.8 |  |  |  |
| warning earcon | beat | waiting | 14.2 | 1 | 114.2 | 100.0 | warning | -18.1 | -8.8 |
| warning earcon again | beat | waiting | 13.3 | 1 | 113.3 | 100.0 | warning | -19.0 | -9.6 |
| confirmed | enter | waiting → thinking | 16.5 | 1 | 149.8 | 133.3 |  |  |  |
| late duplicate ask (confirmed) | door | thinking | — | 0 | — | — |  |  |  |
| purchase earcon | beat | thinking | 9.6 | 1 | 109.6 | 100.0 | purchase | -22.7 | -13.4 |
| task done | exit | thinking → idle | 23.2 | 1 | 121.1 | 97.9 | success | -9.1 | 0.3 |
| key-down → listening (2) | enter | idle → listening | 16.4 | 1 | 141.4 | 125.0 | listening | -15.9 | -6.6 |
| key-up → heard (2) | enter | listening → thinking | 11.3 | 1 | 144.6 | 133.3 | heard | -21.0 | -11.6 |
| asking (2) | enter | thinking → waiting | 14.4 | 1 | 156.1 | 141.7 |  |  |  |
| cancelled | exit | waiting → stopped | 9.3 | 1 | 100.9 | 91.7 | cancel | -23.0 | -13.7 |
| late duplicate ask (cancelled) | door | stopped | — | 0 | — | — |  |  |  |
| thinking (3) | enter | stopped → thinking | 15.2 | 1 | 140.2 | 125.0 |  |  |  |
| error | enter | thinking → error | 26.9 | 1 | 161.5 | 134.6 | error | -5.4 | 3.9 |
| thinking (4) | enter | error → thinking | 14.7 | 1 | 148.1 | 133.3 |  |  |  |
| add-to-cart earcon | beat | thinking | 14.5 | 1 | 114.5 | 100.0 | add-to-cart | -17.7 | -8.4 |
| checkpoint earcon | beat | thinking | 13.8 | 1 | 113.8 | 100.0 | checkpoint | -18.5 | -9.2 |
| queued earcon | beat | thinking | 10.5 | 1 | 110.5 | 100.0 | queued | -21.8 | -12.5 |
| complete earcon | beat | thinking | 13.7 | 1 | 113.7 | 100.0 | complete | -18.6 | -9.3 |
| attention earcon | beat | thinking | 10.8 | 1 | 110.8 | 100.0 | attention | -21.5 | -12.2 |
| blocked | enter | thinking → error | 8.7 | 1 | 142.0 | 133.3 | blocked | -23.6 | -14.2 |
| thinking (5) | enter | error → thinking | 11.9 | 1 | 145.3 | 133.3 |  |  |  |
| stopped | exit | thinking → stopped | 15.9 | 1 | 99.3 | 83.3 | stop | -16.4 | -7.0 |
| idle | exit | stopped → idle | 12.4 | 1 | 104.1 | 91.7 |  |  |  |

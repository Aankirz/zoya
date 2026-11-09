| step | kind | states | first frame ms | frames | settled ms | motion ms | sound | skew high | skew low |
|---|---|---|---|---|---|---|---|---|---|
| start idle | exit | idle | — | 0 | — | — |  |  |  |
| key-down → listening | enter | idle → listening | 22.8 | 1 | 153.5 | 130.7 | listening | -9.5 | -0.2 |
| you said, Hindi | enter | listening | 12.4 | 1 | 129.1 | 116.7 |  |  |  |
| key-up → heard + working | enter | listening → thinking | 15.6 | 1 | 132.3 | 116.7 | heard | -16.7 | -7.3 |
| step update, same state | enter | thinking → acting | 24.4 | 1 | 126.9 | 102.5 |  |  |  |
| step update again | enter | acting | 14.1 | 1 | 14.1 | 0.0 |  |  |  |
| speaking, long | enter | acting → speaking | 22.6 | 1 | 144.0 | 121.5 |  |  |  |
| asking while speaking | enter | speaking → waiting | 56.8 | 1 | 188.2 | 131.4 |  |  |  |
| warning earcon | beat | waiting | 12.7 | 1 | 112.7 | 100.0 | warning | -19.5 | -10.2 |
| cancel by timeout | exit | waiting → stopped | 26.7 | 1 | 149.2 | 122.6 | cancel | -5.6 | 3.7 |
| late ask after timeout | door | stopped | — | 0 | — | — |  |  |  |
| key-down → listening (2) | enter | stopped → listening | 14.5 | 1 | 139.5 | 125.0 | listening | -17.8 | -8.5 |
| key-up → heard (2) | enter | listening → thinking | 25.5 | 1 | 159.3 | 133.8 | heard | -6.8 | 2.5 |
| aim and act | ring | thinking | 26.1 | 1 | 114.4 | 88.3 |  |  |  |
| asking (gift) | enter | thinking → waiting | 19.6 | 1 | 150.9 | 131.2 |  |  |  |
| duplicate ask while asking | door | waiting | — | 0 | — | — |  |  |  |
| confirmed | enter | waiting → thinking | 15.6 | 1 | 149.0 | 133.3 |  |  |  |
| purchase earcon | beat | thinking | 10.5 | 1 | 110.5 | 100.0 | purchase | -21.8 | -12.5 |
| task cancelled | exit | thinking → stopped | 14.1 | 1 | 97.5 | 83.3 |  |  |  |
| late ask after task ended | door | stopped | — | 0 | — | — |  |  |  |
| speaking, Hindi | enter | stopped | 15.0 | 1 | 140.0 | 125.0 |  |  |  |
| failed | enter | stopped → error | 29.0 | 1 | 153.0 | 124.0 |  |  |  |
| idle | exit | error → idle | 16.0 | 1 | 107.7 | 91.7 |  |  |  |

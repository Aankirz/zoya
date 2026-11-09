| step | kind | states | first frame ms | frames | settled ms | motion ms | sound | skew high | skew low |
|---|---|---|---|---|---|---|---|---|---|
| start idle | exit | idle | — | 0 | — | — |  |  |  |
| key-down → listening | enter | idle → listening | 15.4 | 1 | 148.7 | 133.3 | listening | -16.9 | -7.6 |
| you said, Hindi | enter | listening | 11.0 | 1 | 136.0 | 125.0 |  |  |  |
| key-up → heard + working | enter | listening → thinking | 14.2 | 1 | 139.2 | 125.0 | heard | -18.1 | -8.7 |
| step update, same state | enter | thinking → acting | 23.9 | 1 | 127.5 | 103.6 |  |  |  |
| step update again | enter | acting | 154.2 | 1 | 154.2 | 0.0 |  |  |  |
| speaking, long | enter | acting → speaking | 32.3 | 1 | 147.8 | 115.5 |  |  |  |
| asking while speaking | enter | speaking → waiting | 89.1 | 1 | 221.3 | 132.2 |  |  |  |
| warning earcon | beat | waiting | 17.9 | 2 | 117.9 | 100.0 | warning | -14.4 | -5.0 |
| cancel by timeout | exit | waiting → stopped | 27.6 | 1 | 149.1 | 121.5 | cancel | -4.7 | 4.6 |
| late ask after timeout | door | stopped | — | 0 | — | — |  |  |  |
| key-down → listening (2) | enter | stopped → listening | 14.8 | 1 | 139.8 | 125.0 | listening | -17.5 | -8.2 |
| key-up → heard (2) | enter | listening → thinking | — | 0 | — | — | heard |  |  |
| aim and act | ring | thinking | 34.1 | 2 | 127.3 | 93.2 |  |  |  |
| asking (gift) | enter | thinking → waiting | 17.1 | 2 | 150.5 | 133.3 |  |  |  |
| duplicate ask while asking | door | waiting | — | 0 | — | — |  |  |  |
| confirmed | enter | waiting → thinking | 42.7 | 1 | 203.4 | 160.7 |  |  |  |
| purchase earcon | beat | thinking | 44.8 | 1 | 117.6 | 72.8 | purchase | 12.5 | 21.8 |
| task cancelled | exit | thinking → stopped | 209.6 | 1 | 553.3 | 343.7 |  |  |  |
| late ask after task ended | door | stopped | — | 0 | — | — |  |  |  |
| speaking, Hindi | enter | stopped | 29.3 | 1 | 149.2 | 119.9 |  |  |  |
| failed | enter | stopped → error | 34.6 | 1 | 158.0 | 123.4 |  |  |  |
| idle | exit | error → idle | 33.7 | 2 | 118.0 | 84.3 |  |  |  |

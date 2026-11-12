# Message-mode regression report

Generated : 2026-11-13 01:51:11  
Simulator : Icarus Verilog  
Reference : Python golden model (`golden_model.write_result`)

Cases: 46, passed: 46, failed: 0

Each case: messages cut into DATA_WIDTH-bit slots, frame f = slot f of every channel, a finished channel sends 0. PASS = the RTL result file equals the golden result file (except the '# source' line) and the testbench self-check reports 0 errors.

| # | Case | Size | Frames | Last output (cycle) | Messages | TB errors | Files equal | Result |
|---|------|------|--------|---------------------|----------|-----------|-------------|--------|
| 0 | case1 | 4 x 8 | 1 | 33 | `a5, 3c, f0, 5a` | 0 | yes | PASS |
| 1 | case2 | 4 x 8 | 8 | 257 | `0123456789abcdef, deadbeef, cafe, 5a` | 0 | yes | PASS |
| 2 | case3 | 4 x 16 | 4 | 257 | `0123456789abcdef, deadbeef, cafe, 5a` | 0 | yes | PASS |
| 3 | case4 | 4 x 8 | 4 | 129 | `00000000, ffffffff, 0f0f0f0f, f0f0f0f0` | 0 | yes | PASS |
| 4 | case5 | 8 x 8 | 2 | 129 | `0123, 4567, 89ab, cdef, 1122, 3344, 5566, 7788` | 0 | yes | PASS |
| 5 | case6 | 3 x 12 | 3 | 109 | `abcdef123, 456, 789abc` | 0 | yes | PASS |
| 6 | rand_4x8_000 | 4 x 8 | 12 | 385 | `283fe, c63f0cd0e873a000, 0c6d07ef7b77e90d3593a, d699fc1f7...` | 0 | yes | PASS |
| 7 | rand_4x8_001 | 4 x 8 | 8 | 257 | `c557067cbb, 80c46d1fb6dfbdb, a, 0755281220e0878` | 0 | yes | PASS |
| 8 | rand_4x8_002 | 4 x 8 | 12 | 385 | `5b92, 58589e, aff309cad68386d070c415e, d7e70cad1946192299...` | 0 | yes | PASS |
| 9 | rand_4x8_003 | 4 x 8 | 11 | 353 | `16e51c6b36d6f3c9f0, c9056a4ad68, 3cbf721245568a8baa397f, ...` | 0 | yes | PASS |
| 10 | rand_4x8_004 | 4 x 8 | 7 | 225 | `44a3c2728b93e, 319002d31, 7d53e57, 3dc98f` | 0 | yes | PASS |
| 11 | rand_4x8_005 | 4 x 8 | 11 | 353 | `36a1009aeca, 22ae386fb8569, 7b282e2, a7c91a5a97a327707c282` | 0 | yes | PASS |
| 12 | rand_4x8_006 | 4 x 8 | 12 | 385 | `2009bff43a25544a9394641a, 659d51782ed8ee0ca58f, d, 01b444...` | 0 | yes | PASS |
| 13 | rand_4x8_007 | 4 x 8 | 12 | 385 | `aff7da87, 2b, 6999b5, e23c548d61fcbc512838242` | 0 | yes | PASS |
| 14 | rand_4x8_008 | 4 x 8 | 11 | 353 | `7cdc5ae4f63dd39, 7c06e0078, 5946898, e5bfd36c693030942b9dba` | 0 | yes | PASS |
| 15 | rand_4x8_009 | 4 x 8 | 12 | 385 | `3, eb9caf3cc6086ed, 95e6b0cdca2f790d4c8520b8, d94e8f5e183...` | 0 | yes | PASS |
| 16 | rand_4x16_000 | 4 x 16 | 6 | 385 | `67a822b, 1598b7cc5f8a787, 0cad78625e48e544eb9c73, 69237ca...` | 0 | yes | PASS |
| 17 | rand_4x16_001 | 4 x 16 | 6 | 385 | `7fec5779ec6e8, f362100fac9, c5400c4, 1c842e90114183d260f486` | 0 | yes | PASS |
| 18 | rand_4x16_002 | 4 x 16 | 6 | 385 | `eca887715bd1bd6d282853, 16d11, 2fb3a141e4ce0828a291c, 8a` | 0 | yes | PASS |
| 19 | rand_4x16_003 | 4 x 16 | 6 | 385 | `48c393d76aacf34e0956bca3, b4219ad9ab8a03, aaa2e, febc2141f` | 0 | yes | PASS |
| 20 | rand_4x16_004 | 4 x 16 | 6 | 385 | `87abbc9ea50487435d1, 8368, 226, 5d0bf976f7deb6f28d60c` | 0 | yes | PASS |
| 21 | rand_4x16_005 | 4 x 16 | 5 | 321 | `f2cd1be069039a9dd, 9e94e4580d1bdc90220c, e8bface3f, 4d405...` | 0 | yes | PASS |
| 22 | rand_4x16_006 | 4 x 16 | 6 | 385 | `d8daf6fcd2246470384f3c50, d16, db13d3885f162c3e9f, 3f34c6...` | 0 | yes | PASS |
| 23 | rand_4x16_007 | 4 x 16 | 6 | 385 | `30b81e937887d448, d14d88f, 98f6fbf7a55e41a46affa34, 87215` | 0 | yes | PASS |
| 24 | rand_4x16_008 | 4 x 16 | 6 | 385 | `3769da0097278a8c03ab43, 41b2239a7, 1b024cb73, a80a3b48c2f...` | 0 | yes | PASS |
| 25 | rand_4x16_009 | 4 x 16 | 5 | 321 | `80888f4c3b2b09, 44246fab954cec3, 489004c3e0dd8bdce13f, 01` | 0 | yes | PASS |
| 26 | rand_8x8_000 | 8 x 8 | 12 | 769 | `4b8b, 773b531adb81ddcb, ae741a35fa, 30f6c5c737aa7efbf6dec...` | 0 | yes | PASS |
| 27 | rand_8x8_001 | 8 x 8 | 12 | 769 | `8852b, 4888bc8e044, 7626d74ec, 622410ccd4427c496cb5794, f...` | 0 | yes | PASS |
| 28 | rand_8x8_002 | 8 x 8 | 11 | 705 | `cb67b2a1e1549f12c, c9c, bf1f0d9a4, 82bdc03103aab1b2f2ea, ...` | 0 | yes | PASS |
| 29 | rand_8x8_003 | 8 x 8 | 12 | 769 | `1beab70, f, 58, 10725166e97fbac265, 9dfb0f0, daa2, d6ffef...` | 0 | yes | PASS |
| 30 | rand_8x8_004 | 8 x 8 | 11 | 705 | `9da70, 5b99cde26d71777cc649b, 9, f540bdafa398d09, f37, 8d...` | 0 | yes | PASS |
| 31 | rand_8x8_005 | 8 x 8 | 12 | 769 | `1a42, 4719b12e6753161, 32798d7186abbecc2d7fa537, d89, bde...` | 0 | yes | PASS |
| 32 | rand_8x8_006 | 8 x 8 | 12 | 769 | `bbba35c186179ac7b1790634, b845729d, f5b6d286744605f, 51b2...` | 0 | yes | PASS |
| 33 | rand_8x8_007 | 8 x 8 | 12 | 769 | `985a4b3cb6ce4f71722, ff, a5fc0ce5b1bbe792eb654e1, a5ff071...` | 0 | yes | PASS |
| 34 | rand_8x8_008 | 8 x 8 | 11 | 705 | `16efc9b5850127eae, 3c1e8dea35c, df4a4b4676e433d1e4, a8c0c...` | 0 | yes | PASS |
| 35 | rand_8x8_009 | 8 x 8 | 12 | 769 | `ac6, 93d0b2d435a4cda86655543, 4d4aa40b577ff12, f46b4, b2c...` | 0 | yes | PASS |
| 36 | rand_3x12_000 | 3 x 12 | 7 | 253 | `e4b1b373d40b4490f, 0f2d2f34cd7cfae326b33, 36320d729f1d` | 0 | yes | PASS |
| 37 | rand_3x12_001 | 3 x 12 | 7 | 253 | `9c108fe78afe185ee9, 5acdcf79024f3b89943, 4e1efab40682e9080` | 0 | yes | PASS |
| 38 | rand_3x12_002 | 3 x 12 | 7 | 253 | `c33ae2fa16513139654, 62bd8497, 810` | 0 | yes | PASS |
| 39 | rand_3x12_003 | 3 x 12 | 5 | 181 | `9fdd2561ddbb45, 71b2ea67, 4c3f0f989` | 0 | yes | PASS |
| 40 | rand_3x12_004 | 3 x 12 | 3 | 109 | `4c1ce04, f39d6a37, f35fbdcd` | 0 | yes | PASS |
| 41 | rand_3x12_005 | 3 x 12 | 7 | 253 | `c, d419c, d368fd83a4803be83942` | 0 | yes | PASS |
| 42 | rand_3x12_006 | 3 x 12 | 5 | 181 | `c0f4cf70c1d271, 291b12219b92fba, b7a776` | 0 | yes | PASS |
| 43 | rand_3x12_007 | 3 x 12 | 4 | 145 | `9a90f87475, 8c6, 52ac6` | 0 | yes | PASS |
| 44 | rand_3x12_008 | 3 x 12 | 6 | 217 | `1e6c39, 9ea22273, ee05ed360796998b8` | 0 | yes | PASS |
| 45 | rand_3x12_009 | 3 x 12 | 4 | 145 | `100e162ae9, 7360, 40e07f5` | 0 | yes | PASS |

Status: PASS

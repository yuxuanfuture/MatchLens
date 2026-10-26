(function () {
  const moment = (kicker, headlineEn, headlineZh, copyEn, copyZh, evidence, confidence = 98) => ({
    kicker,
    confidence,
    headline: { en: headlineEn, zh: headlineZh },
    copy: { en: copyEn, zh: copyZh },
    evidence
  });

  window.MATCHLENS_SCENARIOS = [
    {
      id: "high-press",
      label: "High press",
      subtitle: "Regain → finish",
      duration: 18,
      initialStats: { possession: [51, 49], xg: [0.63, 0.46], pressure: 0.34 },
      teams: {
        home: { name: "Northbridge FC", short: "NBR", color: "#52d3ff", score: 0 },
        away: { name: "Riverside Athletic", short: "RIV", color: "#ff8c5a", score: 0 }
      },
      events: [
        { t: 0, minute: 62, second: 4, team: "away", type: "pass", player: "A5", recipient: "A6", start: [82, 19], end: [71, 26], success: true, pressure: 0.28, momentum: -12 },
        { t: 1.4, minute: 62, second: 7, team: "home", type: "pressure", player: "H9", start: [69, 27], end: [70, 27], success: true, pressure: 0.66, momentum: 4 },
        { t: 2.8, minute: 62, second: 10, team: "away", type: "pass", player: "A6", recipient: "A4", start: [71, 26], end: [79, 40], success: true, pressure: 0.71, momentum: 11 },
        { t: 4.2, minute: 62, second: 13, team: "home", type: "pressure", player: "H11", start: [77, 42], end: [79, 40], success: true, pressure: 0.86, momentum: 23,
          moment: moment(
            "PRESSURE SHIFT",
            "Northbridge move the regain line 11 metres higher",
            "Northbridge 将夺回球权线前移了 11 米",
            "Three coordinated pressures force Riverside backwards and isolate their right centre-back.",
            "三次协同压迫迫使 Riverside 回传，并孤立了他们的右中卫。",
            ["3 pressures / 28s", "+11m regain line", "86% pressure"], 97
          )
        },
        { t: 5.6, minute: 62, second: 16, team: "away", type: "pass", player: "A4", recipient: "A2", start: [79, 40], end: [70, 56], success: false, pressure: 0.91, momentum: 38 },
        { t: 7, minute: 62, second: 18, team: "home", type: "interception", player: "H7", start: [69, 54], end: [70, 56], success: true, pressure: 0.9, momentum: 54,
          moment: moment(
            "HIGH-VALUE REGAIN",
            "The press creates a 4v3 before Riverside can reset",
            "压迫制造出 4 对 3，Riverside 来不及重组",
            "The turnover arrives 24 metres from goal with four Northbridge attackers already ahead of the ball.",
            "球权在距离球门 24 米处转换，Northbridge 已有四名进攻球员越过球线。",
            ["Regain at 24m", "4v3 overload", "evt_006 verified"], 99
          )
        },
        { t: 8.4, minute: 62, second: 20, team: "home", type: "carry", player: "H7", start: [70, 56], end: [78, 48], success: true, pressure: 0.62, momentum: 62 },
        { t: 9.8, minute: 62, second: 22, team: "home", type: "pass", player: "H7", recipient: "H10", start: [78, 48], end: [83, 35], success: true, pressure: 0.54, momentum: 69 },
        { t: 11.2, minute: 62, second: 24, team: "home", type: "shot", player: "H10", start: [83, 35], end: [98, 31], success: false, xg: 0.28, ballSpeed: 91, pressure: 0.4, momentum: 76 },
        { t: 12.6, minute: 62, second: 26, team: "home", type: "rebound", player: "H9", start: [91, 31], end: [92, 34], success: true, pressure: 0.22, momentum: 83 },
        { t: 14, minute: 62, second: 27, team: "home", type: "shot", player: "H9", start: [92, 34], end: [101, 35], success: true, xg: 0.44, ballSpeed: 78, pressure: 0.18, momentum: 94, score: [1, 0],
          moment: moment(
            "WHY IT MATTERS",
            "Goal: the finish is the last step of a 23-second press",
            "进球：终结只是 23 秒压迫的最后一步",
            "Northbridge score before Riverside complete a single progressive pass after the pressure begins.",
            "从压迫开始到进球，Riverside 没能完成一次向前传球。",
            ["23s press-to-goal", "0 progressive passes", "0.72 sequence xG"], 99
          )
        },
        { t: 16.2, minute: 62, second: 34, team: "away", type: "restart", player: "A9", start: [52.5, 34], end: [46, 34], success: true, pressure: 0.12, momentum: 72 }
      ]
    },
    {
      id: "counter",
      label: "Counter attack",
      subtitle: "Corner → goal in 9s",
      duration: 18,
      homeAttacks: "left",
      initialStats: { possession: [47, 53], xg: [0.82, 1.04], pressure: 0.42 },
      teams: {
        home: { name: "Eastgate United", short: "EGU", color: "#d7ff4b", score: 1 },
        away: { name: "Harbour City", short: "HBC", color: "#b68cff", score: 1 }
      },
      events: [
        { t: 0, minute: 78, second: 42, team: "away", type: "corner", player: "A11", start: [103, 2], end: [89, 33], success: true, pressure: 0.44, momentum: -34 },
        { t: 1.4, minute: 78, second: 44, team: "home", type: "claim", player: "H1", start: [96, 34], end: [94, 34], success: true, pressure: 0.63, momentum: -10 },
        { t: 2.8, minute: 78, second: 45, team: "home", type: "throw", player: "H1", recipient: "H7", start: [94, 34], end: [74, 57], success: true, pressure: 0.51, momentum: 9,
          moment: moment(
            "TRANSITION WINDOW",
            "Harbour have eight players ahead of the ball",
            "Harbour 有八名球员处在球的前方",
            "Eastgate's goalkeeper releases in 1.2 seconds, attacking the largest defensive imbalance of the match.",
            "Eastgate 门将在 1.2 秒内发动进攻，利用本场最大的防守失衡。",
            ["8 players committed", "1.2s release", "Open right channel"], 98
          )
        },
        { t: 4.2, minute: 78, second: 47, team: "home", type: "carry", player: "H7", start: [74, 57], end: [61, 52], success: true, speed: 31.4, pressure: 0.32, momentum: 29 },
        { t: 5.6, minute: 78, second: 48, team: "home", type: "pass", player: "H7", recipient: "H10", start: [61, 52], end: [48, 36], success: true, pressure: 0.28, momentum: 44 },
        { t: 7, minute: 78, second: 49, team: "home", type: "turn", player: "H10", start: [48, 36], end: [47, 33], success: true, pressure: 0.49, momentum: 51 },
        { t: 8.4, minute: 78, second: 50, team: "home", type: "pass", player: "H10", recipient: "H11", start: [47, 33], end: [25, 16], success: true, pressure: 0.56, momentum: 64,
          moment: moment(
            "LINE-BREAKING PASS",
            "One pass removes four defenders from the play",
            "一脚传球让四名防守球员退出防守",
            "The diagonal travels 27 metres into the space vacated by Harbour's attacking full-back.",
            "这脚 27 米斜传打入 Harbour 进攻型边后卫留下的空当。",
            ["27m progressive pass", "4 defenders bypassed", "2v1 created"], 97
          )
        },
        { t: 9.8, minute: 78, second: 51, team: "home", type: "carry", player: "H11", start: [25, 16], end: [17, 25], success: true, speed: 33.1, pressure: 0.22, momentum: 78 },
        { t: 11.2, minute: 78, second: 52, team: "home", type: "cross", player: "H11", recipient: "H9", start: [17, 25], end: [9, 36], success: true, pressure: 0.37, momentum: 86 },
        { t: 12.6, minute: 78, second: 53, team: "home", type: "shot", player: "H9", start: [9, 36], end: [2, 32], success: true, xg: 0.39, ballSpeed: 84, pressure: 0.41, momentum: 96, score: [2, 1],
          moment: moment(
            "COUNTER COMPLETE",
            "Nine seconds, four actions, one decisive goal",
            "九秒、四次推进、一次决定性进球",
            "Eastgate turn a defensive corner into the highest-quality open-play chance of the second half.",
            "Eastgate 将一次防守角球转化为下半场质量最高的运动战机会。",
            ["9.1s transition", "4 attacking actions", "0.39 xG"], 99
          )
        },
        { t: 14.8, minute: 78, second: 58, team: "home", type: "celebration", player: "H9", start: [7, 34], end: [12, 18], success: true, pressure: 0.05, momentum: 88 },
        { t: 16.2, minute: 79, second: 5, team: "away", type: "restart", player: "A9", start: [52.5, 34], end: [58, 34], success: true, pressure: 0.14, momentum: 63 }
      ]
    },
    {
      id: "momentum",
      label: "Momentum swing",
      subtitle: "Substitution impact",
      duration: 20,
      initialStats: { possession: [44, 56], xg: [0.41, 0.88], pressure: 0.38 },
      teams: {
        home: { name: "Atlas Sporting", short: "ATL", color: "#ffcf5a", score: 0 },
        away: { name: "Union 1908", short: "UNI", color: "#5ae6b8", score: 1 }
      },
      events: [
        { t: 0, minute: 83, second: 10, team: "home", type: "substitution", player: "H17", start: [50, 66], end: [49, 54], success: true, pressure: 0.2, momentum: -42,
          moment: moment(
            "TACTICAL CHANGE",
            "Atlas add a second runner between the lines",
            "Atlas 在两条防线之间增加第二名穿插球员",
            "The new shape moves from 4-3-3 to 3-2-5 and pins both Union full-backs deeper.",
            "新阵型由 4-3-3 变为 3-2-5，迫使 Union 两名边后卫同时回撤。",
            ["Shape: 3-2-5", "+1 central runner", "Both full-backs pinned"], 96
          )
        },
        { t: 1.6, minute: 83, second: 35, team: "home", type: "pass", player: "H6", recipient: "H17", start: [44, 36], end: [62, 31], success: true, pressure: 0.47, momentum: -26 },
        { t: 3.2, minute: 83, second: 39, team: "home", type: "carry", player: "H17", start: [62, 31], end: [72, 30], success: true, pressure: 0.56, momentum: -9 },
        { t: 4.8, minute: 83, second: 42, team: "home", type: "shot", player: "H17", start: [75, 30], end: [99, 29], success: false, xg: 0.12, ballSpeed: 88, pressure: 0.63, momentum: 8 },
        { t: 6.4, minute: 84, second: 8, team: "home", type: "recovery", player: "H3", start: [54, 58], end: [57, 56], success: true, pressure: 0.7, momentum: 18 },
        { t: 8, minute: 84, second: 12, team: "home", type: "cross", player: "H3", recipient: "H9", start: [72, 59], end: [88, 36], success: true, pressure: 0.51, momentum: 33 },
        { t: 9.6, minute: 84, second: 14, team: "home", type: "shot", player: "H9", start: [88, 36], end: [100, 38], success: false, xg: 0.21, ballSpeed: 73, pressure: 0.48, momentum: 46,
          moment: moment(
            "MOMENTUM FLIP",
            "Atlas have created more threat in 64 seconds than the previous 20 minutes",
            "Atlas 在 64 秒内制造的威胁超过此前 20 分钟",
            "The substitution produces two box entries and 0.33 xG while Union fail to cross halfway.",
            "换人后 Atlas 完成两次禁区进入并累计 0.33 xG，Union 尚未越过中线。",
            ["0.33 xG / 64s", "2 box entries", "0 Union exits"], 98
          )
        },
        { t: 11.2, minute: 84, second: 31, team: "away", type: "clearance", player: "A5", start: [91, 39], end: [64, 48], success: true, pressure: 0.82, momentum: 52 },
        { t: 12.8, minute: 84, second: 34, team: "home", type: "interception", player: "H8", start: [63, 46], end: [64, 48], success: true, pressure: 0.87, momentum: 67 },
        { t: 14.4, minute: 84, second: 36, team: "home", type: "pass", player: "H8", recipient: "H17", start: [64, 48], end: [78, 39], success: true, pressure: 0.69, momentum: 76 },
        { t: 16, minute: 84, second: 38, team: "home", type: "pass", player: "H17", recipient: "H9", start: [78, 39], end: [90, 33], success: true, pressure: 0.55, momentum: 86 },
        { t: 17.6, minute: 84, second: 39, team: "home", type: "shot", player: "H9", start: [90, 33], end: [101, 34], success: true, xg: 0.36, ballSpeed: 82, pressure: 0.37, momentum: 98, score: [1, 1],
          moment: moment(
            "IMPACT CONFIRMED",
            "The substitute creates the equaliser with his third line-breaking action",
            "替补球员第三次穿透防线，直接创造扳平球",
            "Every Atlas attack since the change has passed through H17 before reaching the penalty area.",
            "换人后的每次 Atlas 进攻，都经过 H17 才进入禁区。",
            ["3 line breaks", "1 pre-assist", "+57 momentum swing"], 99
          )
        },
        { t: 19, minute: 84, second: 46, team: "away", type: "restart", player: "A9", start: [52.5, 34], end: [57, 34], success: true, pressure: 0.1, momentum: 74 }
      ]
    }
  ];
})();

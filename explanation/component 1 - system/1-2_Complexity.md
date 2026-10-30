# Complexity, explained simply — 複雜度，簡單說明

We have already seen what a system is: parts, connections, and a whole that does something none of the parts can do alone. This guide answers the next question, the one that matters most in practice: why are some systems easy to deal with and others maddeningly hard? The short answer is that complexity is not about how many parts a system has. A watch and a city both have many parts. Complexity is about how the parts affect each other. In a complex system, the behavior that matters lives in the relationships between the parts, not in the parts themselves, so you cannot understand or predict the whole by studying the parts one at a time. The whole really is more than the sum of its parts. And the first lesson, which the rest of this guide builds on, is this: before you touch any problem, figure out what kind of problem it is.

我們已經看過系統是什麼：部件、連結，以及一個能做到任何部件獨力做不到的事情的整體。這份指南回答下一個問題，也是實務上最重要的問題：為什麼有些系統容易應付，有些卻難到讓人抓狂？簡短的答案是：複雜度不在於系統有多少部件。手錶和城市都有很多部件。複雜度在於部件之間如何互相影響。在複雜系統中，真正要緊的行為存在於部件之間的關係裡，而不在部件本身，因此你無法靠著逐一研究部件來理解或預測整體。整體確實大於各部分的總和。而第一課——本指南後文都建立在它之上——是：在你動手處理任何問題之前，先搞清楚它是哪一種問題。

## 1. Simple, complicated, complex, and one rung higher — 簡單、繁複、複雜，以及更高一階

Ask one question about anything you face: if I analyze hard enough, can I know the outcome in advance? The answer sorts things into kinds. This sorting is often told as the cake, rocket, child story, which the health policy researchers Marc Glouberman and Henry Zimmerman laid out in a 2002 discussion paper for the Commission on the Future of Health Care in Canada.

對你面對的任何事物問一個問題：如果我分析得夠透徹，能不能事先知道結果？這個答案把事物分門別類。這套分類常以「蛋糕、火箭、孩子」的故事來講述，由健康政策研究者 Marc Glouberman 與 Henry Zimmerman 在 2002 年為加拿大醫療保健未來委員會撰寫的討論文件中提出。

Baking a cake is simple. Clear rules, the recipe, produce a predictable, repeatable result most of the time. Expertise can improve the cake, but even a novice following the recipe can expect to succeed. The context can vary quite a bit, a different oven, different flour, and it still works, because the context has only a limited effect on the result.

烤蛋糕是簡單的。清楚的規則——食譜——大多時候產生可預期、可重複的結果。專業能把蛋糕做得更好，但即使是新手照著食譜做，也有成功的把握。情境可以有相當大的變化——不同的烤箱、不同的麵粉——它仍然行得通，因為情境對結果只有有限的影響。

Sending a rocket to the moon is complicated. The basic principles are well understood, but applying them takes complicated calculations, precision engineering, and careful planning. Each launch is a massive effort needing specialized knowledge, and even then some uncertainty remains. Success is less guaranteed than with a cake, though experience and expertise make later launches better. The context matters more here than it does for baking.

把火箭送上月球是繁複的。基本原理已被充分理解，但應用它們需要繁複的計算、精密的工程和細心的規劃。每次發射都是需要專業知識的巨大工程，即便如此仍殘留著一些不確定性。成功不像烤蛋糕那樣有把握，不過經驗與專業能讓後來的發射表現更好。在這裡，情境比烤蛋糕重要得多。

Raising a child is complex. No set of rules or recipes can guarantee a good outcome, and deciding what a "good outcome" even means is itself a complex question. Each child is unique. What works for one child may fail for another, even within the same family, even with twins. Experience helps, but it always has to be adapted to the individual child and their situation, and expertise alone is not enough.

養育孩子是複雜的。沒有任何一套規則或食譜能保證好結果，而「好結果」到底意味著什麼，本身就是一個複雜的問題。每個孩子都是獨一無二的。對一個孩子有效的方法，對另一個可能失效，即使在同一個家庭裡、即使是雙胞胎也不例外。經驗有幫助，但它永遠必須因應個別孩子及其處境做調整，光有專業是不夠的。

And still there is something above the child: the *wicked problems*. A wicked problem is one you cannot fully define until you have already solved it, one with no finish line and no pass-or-fail test, where every attempt to fix it changes the problem itself. Ending poverty is the standing example, and the UN's 17 Sustainable Development Goals, taken together, spell out what that looks like in practice. The goals are:

在孩子之上還有更高的東西：「棘手問題」。一個棘手問題是你在解決它之前無法完全定義它的問題，它沒有終點線、沒有及格與否的測試，而且每次試圖修補它都會改變問題本身。終結貧窮是經典的例子，而聯合國的 17 項永續發展目標合在一起，具體說明了那在實務中是什麼模樣。目標如下：

1. No poverty
   消除貧困
2. Zero hunger
   消除飢餓
3. Good health and well-being
   良好健康與福祉
4. Quality education
   優質教育
5. Gender equality
   性別平等
6. Clean water and sanitation
   清潔飲水與衛生設施
7. Affordable and clean energy
   可負擔的清潔能源
8. Decent work and economic growth
   就業與經濟成長
9. Industry, innovation and infrastructure
   產業、創新與基礎建設
10. Reduced inequalities
    減少不平等
11. Sustainable cities and communities
    永續城鄉
12. Responsible consumption and production
    負責任的消費與生產
13. Climate action
    氣候行動
14. Life below water
    海洋生態
15. Life on land
    陸域生態
16. Peace, justice, and strong institutions
    和平、正義與健全制度
17. Partnerships for the goals
    夥伴關係

That is not one complex system but many complex systems coupled together, and that coupling is what makes it so much harder:

那不是單一個複雜系統，而是許多複雜系統耦合在一起，而這種耦合正是它困難得多的原因：

- The goals trade off against each other. Cheap energy pushes against climate action. More food production pushes against biodiversity. Every pull has cross-effects that are hard to predict.

  目標之間互相牽制。便宜的能源與氣候行動相牴觸。更多的糧食生產與生物多樣性相牴觸。每一次拉扯都有難以預測的交叉效應。

- Nobody agrees on the goal. Raising a child has a broadly shared aim. "Sustainable development" does not. Governments, companies, and billions of people define success differently, so the problem itself is argued over.

  沒有人對目標有共識。養育孩子有一個大致共享的目標。「永續發展」沒有。政府、企業和數十億人對成功的定義各不相同，所以連問題本身都在爭論之中。

- No one is in charge. A child has a parent. The goals have fragmented, sometimes adversarial governance and no single decision maker.

  沒有人掌舵。孩子有父母。這些目標面對的是碎片化、有時彼此對立的治理，沒有單一決策者。

- The feedback is delayed, spread out, and sometimes irreversible. Effects unfold over decades, you cannot reset and retry, and some thresholds, once crossed, cannot be undone.

  回饋是延遲的、分散的，有時不可逆。效應在數十年間展開，你無法重置再試一次，而某些閾值一旦跨越就無法回頭。

- There is no finish line. No test tells you when a goal is solved, and every fix redefines the problem somewhere else.

  沒有終點線。沒有測試能告訴你一個目標何時算完成，而每一次修補都在別處重新定義問題。

The whole ladder at a glance:

整把階梯一覽：

| Rung | Example | Same input, same output? | Knowable in advance? | Who is in charge? | What works |
|---|---|---|---|---|---|
| Simple | Cake | Yes | Yes | You | Follow the recipe |
| Complicated | Rocket | Yes, if the parameters are right | Yes, through expert analysis | You, with experts | Engineering and analysis |
| Complex | Child | No | No, only in hindsight | A parent | Sensing, experimenting, adapting |
| Wicked | Ending poverty (the 17 goals) | No | No, and some effects are irreversible | No one | Many actors, small safe-to-fail probes, steering rather than solving |

| 階 | 例子 | 相同輸入，相同輸出？ | 可事先知道？ | 誰掌舵？ | 什麼有效 |
|---|---|---|---|---|---|
| 簡單 | 蛋糕 | 是 | 是 | 你 | 照著食譜做 |
| 繁複 | 火箭 | 是，如果參數正確 | 是，透過專家分析 | 你，加上專家 | 工程與分析 |
| 複雜 | 孩子 | 否 | 否，只有事後才看得出來 | 父母 | 感知、實驗、調適 |
| 棘手 | 終結貧窮（17 項目標） | 否 | 否，且部分效應不可逆 | 沒有人 | 多方參與、小規模的安全失敗試探、以引導代替解決 |

The point of the ladder is that these are different kinds of problem; size is not what separates them. The classic failure is treating each rung as the one below it: baking a rocket like a cake, engineering a child like a rocket, or trying to "raise" the global goals like a child with a plan.

這把階梯的重點在於：這些是不同種類的問題；把它們分開的不是規模。經典的失敗就是把每一階當成比它低的那一階：像烤蛋糕那樣去「烤」火箭、像造火箭那樣用工程去「造」孩子，或試圖拿一份計畫像養孩子那樣去「養」全球目標。

### Five characteristics of a complex system — 複雜系統的五項特性

The ladder tells you when a problem is complex. It also helps to know what a complex system actually does. Complexity theory describes five characteristics that show up again and again: interdependent, dynamic, emergent, non-linear, and adaptive. Knowing them helps you see how they appear in the systems you work with and how they shape anything you try to do inside them.

那把階梯告訴你問題何時是複雜的。但知道複雜系統實際上怎麼運作也有幫助。複雜性理論描述了五項一再出現的特性：相互依存、動態、湧現、非線性、調適。了解它們，能幫助你看見它們如何出現在你所處理的系統裡，以及它們如何塑造你在其中想做的任何事。

A complex system contains many dynamically interconnected parts, and the parts are often complex themselves, which multiplies the complexity. The prison system is one: institutions, individual prisons, and the people inside them, all in continual, dynamic interaction. These parts are both autonomous and interdependent. What each part does affects the others, yet each part also runs on its own needs, behaviors, and goals. Prison officers, prisoners, and justice ministers all belong to the prison system, each with their own agenda, and so do the many social organizations that work inside it. What each actor does affects the others in multiple, dynamic ways. This fluid interdependence creates cause-and-effect relationships that are hard to predict, and so they demand continual adaptation.

複雜系統包含許多動態互連的部件，而部件本身往往也是複雜的，這讓複雜度倍增。監獄系統就是一例：機構、個別監獄、以及裡面的人，全都在持續的動態互動中。這些部件既自主又相互依存。每個部件做的事會影響其他部件，但每個部件也依照自己的需求、行為和目標運作。獄警、囚犯和司法部官員都屬於監獄系統，各有各的盤算，在其中運作的許多社福組織也是如此。每個行動者做的事以多重、動態的方式影響其他人。這種流動的相互依存創造出難以預測的因果關係，因此需要持續的調適。

Here is what each characteristic means, and what it implies for anything you try to change:

以下是每一項特性的意思，以及它對你想改變的任何事情意味著什麼：

| Characteristic | Meaning | Implications |
|---|---|---|
| Interdependent | The parts of the system — people, policies, beliefs, behaviors — are all linked to each other. | The parts an intervention touches are connected to many other parts, and those relationships need to be understood. If you want to change a situation, consider all the other factors connected to that situation. |
| Dynamic | A change in one element changes the parts it is connected to, which changes the parts they are connected to, and so on. | Systems are not static, so any intervention must have a dynamic approach too. Watch how the part you are trying to influence is affected by other changes, and what changes your intervention itself creates. You are not separate from the system but a part of it, so your actions also start chains of cause and effect; ignoring them leads to unintended consequences. |
| Emergent | Continuous interaction between the parts produces new system behaviors that are hard to predict. | To stay effective, sense and respond to new and unexpected shifts as they appear, and work with what emerges. |
| Non-Linear | Change does not follow linear cause and effect; effects can be indirect and disproportionate. | An intervention aims at a target, but many other forces and factors hit that same target, so isolating the impact of one intervention is nearly impossible. Think about contribution to the change, not attribution of the credit. |
| Adaptive | Because of all the above, the whole system — not just its parts — keeps adapting to changes inside and outside it. | The adaptive, changing nature of these systems makes them very hard to control or manage from the top down. There is no single point of entry or control, and every action produces a flood of unpredictable reactions. In the words of the systems theorist Donella Meadows: "We can't control systems... but we can dance with them!" |

| 特性 | 意思 | 對介入的啟示 |
|---|---|---|
| 相互依存 | 系統的部件——人、政策、信念、行為——全都彼此相連。 | 一項介入所觸及的部件與許多其他部件相連，這些關係需要被理解。如果你想改變一個情境，就要考慮與該情境相連的所有其他因素。 |
| 動態 | 一個元素的變化會改變與它相連的部件，再改變與那些部件相連的部件，如此下去。 | 系統不是靜態的，因此任何介入也必須有動態的做法。留意你想影響的部件如何受到其他變化的影響，以及你的介入本身造成了什麼變化。你不是獨立於系統之外，而是系統的一部分，所以你的行動也會啟動一連串因果；忽略它們會帶來非預期的後果。 |
| 湧現 | 部件之間持續的互動會產生難以預測的新系統行為。 | 要保持有效，就要感知並回應新出現的、出乎意料的轉變，並與湧現出來的東西合作。 |
| 非線性 | 變化不遵循線性的因果；效果可能是間接的、不成比例的。 | 一項介入瞄準一個目標，但許多其他力量和因素也打在同一個目標上，所以要隔離出單一介入的影響幾乎不可能。想的是對改變的「貢獻」，而不是把功勞「歸因」於己。 |
| 調適 | 因為以上所有特性的緣故，整個系統——不只是它的部件——會不斷因應內外的變化而調適。 | 這些系統調適、變動的本性，使它們極難由上而下地控制或管理。沒有單一的入口或控制點，而每個行動都會產生大量不可預測的反應。用系統理論家梅多斯的話說：「我們控制不了系統……但我們可以和它們共舞！」 |

Most interventions in the social sector happen inside complex systems, so they inherit all five characteristics. Designing for them means planning less like baking a cake and more like dancing: small moves, constant watching, and readiness to adapt.

社福領域的大多數介入都發生在複雜系統之內，因此它們承襲了全部五項特性。為它們做設計，意味著規劃要比較不像烤蛋糕、而比較像跳舞：小步伐、不斷觀察、隨時準備好調適。

### A deeper version: the ladder of systems — 更深的版本：系統的階梯

The five characteristics in the last section describe how complex systems behave. Boulding's ladder asks a broader question: where do such systems sit among all the kinds of system there are? In 1956 the economist Kenneth Boulding arranged systems into nine levels, in a paper called "General Systems Theory: The Skeleton of Science." Each level adds something genuinely new that the level below does not have:

上一節的五項特性描述複雜系統如何行為。博爾丁的階梯問的是更寬廣的問題：這樣的系統在所有種類的系統之中居於什麼位置？1956 年，經濟學家博爾丁在一篇題為〈一般系統理論：科學的骨架〉的論文中，把系統排成九個層次。每個層次都增加了一些下一層確實沒有的新東西：

| Level | Name | What it means | Example |
|---|---|---|---|
| 1 | Static structures | A fixed pattern in space; nothing moves or changes | A crystal, a map, anatomy |
| 2 | Clockworks | Motion that is predetermined and fully predictable | The solar system, a clock, a machine |
| 3 | Control systems | The system corrects itself through feedback and holds a steady state | A thermostat, a steam engine governor, body temperature |
| 4 | Open, self-maintaining systems | It keeps itself going by taking in matter and energy from its surroundings | A flame, a cell |
| 5 | Plants | The parts divide the labor, and the whole grows and reproduces from a blueprint | A plant |
| 6 | Animals | Mobility, goals, senses, a nervous system, and the ability to learn | An animal |
| 7 | People | Self-awareness, language and symbols, reflection, values, art | A person |
| 8 | Societies and organizations | Many people coordinate through roles, culture, and shared values | A company, a society, an economy |
| 9 | Transcendental systems | The ultimate level, which by definition cannot be known | The transcendent |

| 層次 | 名稱 | 意思 | 例子 |
|---|---|---|---|
| 1 | 靜態結構 | 空間中固定的圖樣；沒有東西移動或改變 | 晶體、地圖、解剖構造 |
| 2 | 機械裝置 | 運動是預先決定的、完全可預測的 | 太陽系、時鐘、機器 |
| 3 | 控制系統 | 系統透過回饋自我修正，維持穩定狀態 | 恆溫器、蒸汽機調速器、體溫 |
| 4 | 開放的自我維持系統 | 它從環境吸收物質與能量讓自己運作下去 | 火焰、細胞 |
| 5 | 植物 | 部件分工，整體依藍圖生長與繁殖 | 一株植物 |
| 6 | 動物 | 移動能力、目標、感官、神經系統，以及學習的能力 | 一隻動物 |
| 7 | 人 | 自我覺察、語言與符號、反思、價值觀、藝術 | 一個人 |
| 8 | 社會與組織 | 許多人透過角色、文化與共同價值協調合作 | 一家公司、一個社會、一個經濟體 |
| 9 | 超越層次 | 終極層次，依定義不可能被認識 | 超越者 |

Read as a whole, the ladder says something stronger than "bigger means more complex." Each level brings a property that does not exist at all below it, so the levels are qualitatively different, not just different in degree. That is why the rungs feel familiar: it is the same intuition as the cake, rocket, and child above, where each rung is a different kind of problem, not a bigger version of the one below. Notice also where the five characteristics enter the ladder: simple feedback appears at level 3, while emergence, non-linear change, and adaptation belong to the levels above it.

整體來讀，這把階梯說的比「越大就越複雜」更強。每個層次帶來一種在它之下的層次完全不存在的特性，所以各層次是性質上的不同，而不只是程度上的不同。這就是為什麼這些階梯讀起來很熟悉：它和前面蛋糕、火箭、孩子是同一種直覺——每一階是不同種類的問題，而不是下一階的放大版。也值得注意五項特性在哪裡進入這把階梯：簡單的迴饋在第 3 層就出現了，而湧現、非線性變化與調適則屬於它之上的那些層次。

Boulding also had a practical purpose in mind. He called general systems theory the "skeleton of science": a way to give every discipline a home on the ladder, expose the gaps between levels, and search for laws that hold across all of them. He saw it as a research agenda, not a finished classification. And he added a test of his own: a level only counts as understood once someone can build a working theory of it. In 1956, the middle of the ladder, especially the cybernetic level 3, was the newest and least settled frontier.

博爾丁心中還有一個實務目的。他把一般系統理論稱為「科學的骨架」：一種讓每門學科都在階梯上有個家、暴露層次之間的落差、並尋找跨越所有層次都成立的定律的方法。他把它視為一項研究議程，而不是一份完成的分類。他還加上一條自己的檢驗標準：一個層次只有在有人能為它建立起一套可運作的理論之後，才算被理解。1956 年，階梯的中段——尤其是控制論的第 3 層——是最新、最未定的前沿。

Two things follow. First, a higher level cannot be explained in the vocabulary of a lower one. A clock cannot explain a living cell. A cell cannot explain an animal chasing a goal. An animal cannot explain a person reflecting on themselves. Second, Boulding noticed that our knowledge gets thinner as you climb: we understand the bottom of the ladder, physics and mechanics, sharply, and the top, societies and beyond, only vaguely. The ladder is also a map of what we do not yet understand.

由此可得兩件事。第一，較高的層次無法用較低層次的詞彙來解釋。時鐘無法解釋一個活的細胞。細胞無法解釋一隻追逐目標的動物。動物無法解釋一個反思自身的人。第二，博爾丁注意到我們的知識越往上越稀薄：我們對階梯底部——物理與力學——理解得很透徹，對頂部——社會及其之上——只有模糊的認識。這把階梯也是我們尚未理解之事的地圖。

That is the terrain, and nobody crossed it easily. The next section is the story of eighty years of trying.

這就是那片地形，沒有人輕易穿越它。下一節是八十年來不斷嘗試的故事。

## 2. Eighty years of trying, and what each attempt taught us — 八十年的嘗試，以及每次嘗試教了我們什麼

One pattern runs through the whole history. Someone invents a method that makes a tangled problem tractable. The method works on the kind of problem it was built for. Then it meets a different kind of problem it cannot handle, and that failure is what pushes the field to invent the next method. The direction of travel is always the same: from believing the system is out there as a measurable object, to believing it lives in people's heads as competing interpretations, to believing it emerges and can only be probed, and finally to the modern view that you match your approach to the situation instead of swearing loyalty to one method.

一個模式貫穿整段歷史。某人發明一種方法，讓糾纏不清的問題變得可處理。這方法在它被打造來處理的那類問題上有效。然後它遇到另一類它處理不了的問題，而那樣的失敗推動領域發明下一個方法。行進的方向始終相同：從相信系統是外在的、可量測的物體，到相信它活在人們腦中、是互相競爭的詮釋，到相信它會湧現、只能被試探，最後到現代觀點——讓方法因應情境做搭配，而不是對某一種方法效忠。

The whole story on one timeline:

整個故事壓成一條時間線：

- 1940s to 1960s: operations research and systems analysis (wartime Britain, then RAND and the Pentagon)

  1940 到 1960 年代：作業研究與系統分析（戰時的英國，然後是蘭德與五角大廈）

- 1948: cybernetics (Norbert Wiener, W. Ross Ashby)

  1948 年：控制論（諾伯特·維納、W. 羅斯·阿什比）

- 1950s: general systems theory (Bertalanffy, Boulding)

  1950 年代：一般系統理論（貝塔蘭菲、博爾丁）

- 1950s to 1970s: system dynamics (Forrester, Meadows; The Limits to Growth, 1972)

  1950 到 1970 年代：系統動力學（福雷斯特、梅多斯；《成長的極限》，1972）

- 1970s: the Viable System Model (Beer); 1973: wicked problems (Rittel and Webber); 1973: resilience thinking (Holling)

  1970 年代：可行系統模型（比爾）；1973 年：棘手問題（里特爾與韋伯）；1973 年：韌性思維（霍林）

- 1970s to 1980s: soft systems methodology (Checkland)

  1970 到 1980 年代：軟系統方法論（切克蘭德）

- 1980s: actor-network theory (Latour, Callon, Law); 1984: the Santa Fe Institute

  1980 年代：行動者網絡理論（拉圖、卡龍、勞）；1984 年：聖塔菲研究院

- 1980s to 1990s: critical systems thinking (Jackson and Flood)

  1980 到 1990 年代：批判系統思維（傑克遜與弗勒德）

- 1998 to 1999: network science (Watts and Strogatz; Barabási and Albert)

  1998 到 1999 年：網絡科學（瓦茨與斯托加茨；巴拉巴西與艾伯特）

- 1999 to 2007: Cynefin (Snowden)

  1999 到 2007 年：Cynefin 框架（斯諾登）

- 2010s onward: no new grand method, on purpose; deep uncertainty, data and AI, and deliberate attempts to change systems

  2010 年代起：刻意不再有新的宏大方法；深度不確定性、資料與人工智慧，以及刻意嘗試改變系統

The sections below walk through these in the order the ideas built on each other: the hard years first, then the soft turn, then the complexity turn and today.

以下各節依照想法彼此堆疊的順序來講述：先是硬性年代，然後是軟性轉向，再來是複雜性轉向與今日。

### The hard years: 1940s to 1970s — 硬性年代：1940 到 1970 年代

#### Cybernetics (1948) — 控制論（1948）

The first of these came out of a wartime problem. During the Second World War, Norbert Wiener worked on aiming guns at moving aircraft and realized the problem was really one of prediction and correction: estimate where the target will be, fire, watch where the shot went, and correct, over and over. The same loop, he saw, is how your body holds its temperature steady and how machines regulate themselves. He made it a general science of control and communication, and W. Ross Ashby added a rule that still matters: a controller can only hold a system steady if it has at least as many possible responses as the system has possible disturbances. Cybernetics could not solve complex problems because it assumed the goal was already given. It tells you how to steer toward a goal, but not where the goal comes from or whose goal it is. That blind spot split the field in two, into the hard branch and the soft branch below.

其中第一項來自一個戰時問題。第二次世界大戰期間，諾伯特·維納研究如何讓火炮瞄準移動中的飛機，並意識到這個問題其實是預測與修正的問題：估計目標會在哪裡、開火、看彈著落在哪裡、然後修正，一再重複。他看出同一個迴圈也是你的身體維持體溫恆定的方式，以及機器自我調節的方式。他把它建立成一門關於控制與通訊的普遍科學，而 W. 羅斯·阿什比補上一條至今仍要緊的規則：一個控制者要有至少和系統可能受到的擾動一樣多的可能回應，才能讓系統保持穩定。控制論無法解決複雜問題，因為它假設目標已經給定。它告訴你如何朝目標前進，卻不告訴你目標從哪裡來、那是誰的目標。這個盲點把領域一分為二，成為下方的硬性分支與軟性分支。

- How it worked: measure the current state, compare it with the goal, act on the difference, and keep repeating.

  運作方式：量測目前狀態、與目標比較、對差異採取行動，然後不斷重複。

- What it gave us: the feedback loop as a pattern shared by machines, bodies, and organizations, plus Ashby's law of requisite variety.

  留給我們什麼：回饋迴圈作為機器、身體與組織共有的模式，以及阿什比的必要多樣性法則。

- Where it broke down: it assumed the goal was already known and agreed, and said nothing about where goals come from or whose they are.

  何處失效：它假設目標已知且有共識，對目標從何而來、是誰的目標隻字未提。

#### General systems theory (1950s) — 一般系統理論（1950 年代）

The sciences had fragmented into narrow specialties, and biologists such as Ludwig von Bertalanffy noticed that very different systems, an organism, a company, a flame, share the same underlying patterns. Boulding's ladder from the last section came out of this effort. The theory stayed a philosophy rather than a technique: it named shared ideas such as open systems and homeostasis but offered no procedure you could run on a real problem, and it made no testable predictions. Saying something was a system explained nothing in particular. That failure pushed the field to build concrete, usable methods, which is where the hard years proper begin.

各門科學已碎裂成狹窄的專門領域，而貝塔蘭菲等生物學家注意到，差異極大的系統——一個有機體、一家公司、一團火焰——共享同樣的底層圖樣。上一節博爾丁的階梯就出自這項努力。這套理論始終是哲學而非技術：它為開放系統、恆定性等共享概念命名，但沒有提供任何能在真實問題上執行的程序，也沒有做出可檢驗的預測。說某個東西是系統，並沒有特別解釋什麼。那樣的失敗推動領域去打造具體、可用的方法，硬性年代真正從這裡開始。

- How it worked: compare systems across fields and name the patterns they share, such as open systems, homeostasis, and equifinality (reaching the same end from different starts).

  運作方式：跨領域比較系統，為它們共享的圖樣命名，例如開放系統、恆定性，以及殊途同歸（從不同起點抵達同一終點）。

- What it gave us: a common vocabulary across disciplines, and Boulding's ladder from the last section.

  留給我們什麼：跨學科的共同詞彙，以及上一節博爾丁的階梯。

- Where it broke down: it stayed conceptual, with no procedure you could run on a real problem and no testable predictions, so saying something was a system explained nothing specific.

  何處失效：它停留在概念層面，沒有可在真實問題上執行的程序、沒有可檢驗的預測，所以說某個東西是系統，並沒有解釋任何具體的東西。

#### Operations research and systems analysis (1940s to 1960s) — 作業研究與系統分析（1940 到 1960 年代）

Wartime Britain gave it its start: scientists such as Patrick Blackett helped the military decide convoy sizes, depth-charge settings, and radar placement with scarce resources. After the war the approach moved to the RAND Corporation and the Pentagon in the 1950s and 1960s, then into industry. The method: build a mathematical model, pick one objective to maximize or minimize, list the constraints, and solve for the optimum. It is genuinely excellent on tame problems such as scheduling, logistics, and routing; GPS finding your shortest path is operations research working as intended. It collapses on messy, political, multi-stakeholder problems for two reasons. It can only optimize what it can measure, so it optimizes the measurable and ignores what matters most, the classic case being the body counts in Vietnam, which counted enemies killed and not whether the war was being won. And even a genuinely optimal answer is often ignored, because it is politically unacceptable or because nobody was consulted, the so-called implementation gap. The wall it hit: you cannot optimize a problem you have not framed correctly, and framing a problem is not a technical act. That wall split the field again, into those who wanted to model the feedback that operations research ignored, which became system dynamics, and those who wanted to work with the human mess, which became the soft methods.

戰時的英國是它的起點：布拉凱特等科學家在資源匱乏下協助軍方決定船隊規模、深水炸彈設定和雷達配置。戰後，這套方法在 1950、1960 年代進入蘭德公司與五角大廈，然後進入產業。方法是：建立一個數學模型、挑一個要最大化或最小化的目標、列出約束條件、解出最優解。在排程、物流、路徑規劃這類馴服的問題上，它確實出色；GPS 幫你找最短路徑，就是作業研究如預期般發揮作用。但在混亂、政治化、多利害關係人的問題上它會崩潰，原因有二。它只能最佳化它能量測的東西，於是它最佳化可量測的、忽略最要緊的——經典案例是越戰的屍體計數，它計算殺死了多少敵人，卻不算這場戰爭是否正在打贏。而且即使是真正最優的答案也常被忽略，因為它在政治上不可接受，或因為根本沒有人被諮詢過——即所謂的落實落差。它撞上的那堵牆是：你無法最佳化一個你沒有正確框定的問題，而框定問題不是一種技術行為。那堵牆再次把領域一分為二：一派想為作業研究所忽略的回饋建立模型，成為系統動力學；另一派想處理人的混亂，成為軟性方法。

- How it worked: build a mathematical model, pick one objective to maximize or minimize, list the constraints, and solve for the optimum.

  運作方式：建立數學模型、挑一個要最大化或最小化的目標、列出約束條件、解出最優解。

- What it gave us: provably good answers on tame problems such as scheduling, logistics, routing, and inventory; GPS route-finding is this working as intended.

  留給我們什麼：在排程、物流、路徑、庫存等馴服問題上可證明為好的答案；GPS 路徑規劃就是它如預期般運作。

- Where it broke down: it optimized only what it could measure (the Vietnam body counts counted enemies killed, not whether the war was being won), and even optimal answers were ignored when politically unacceptable or when nobody was consulted.

  何處失效：它只最佳化它能量測的東西（越戰的屍體計數計算殺死了多少敵人，不算戰爭是否正在打贏），而且當最優答案在政治上不可接受或沒有人被諮詢過時，也會被忽略。

#### System dynamics (1950s to 1970s) — 系統動力學（1950 到 1970 年代）

Jay Forrester created it at MIT, and his group extended it into the 1972 Club of Rome report The Limits to Growth. It explains why complex systems behave counterintuitively. A stock is something that accumulates, such as pollution. A flow is the rate that fills or drains it. Feedback loops with delays mean a change loops back later and changes the flows. You write these as equations, simulate decades ahead, and test policies inside the simulation. The failure: for all its sophistication it is still one quantitative model built by one group of experts, with their chosen boundaries and numbers baked in. It cannot hold several conflicting worldviews at once, its predictions were fiercely contested, and it treats people as mechanical variables with no agency, interpretation, or politics.

福雷斯特在麻省理工學院創立了它，他的團隊把它擴展成 1972 年羅馬俱樂部的報告《成長的極限》。它解釋了為什麼複雜系統的行為違反直覺。存量是會累積的東西，例如污染。流量是注滿或排空它的速率。帶有延遲的迴饋迴圈意味著一個變化在稍後繞回來、改變流量。你把這些寫成方程式、在電腦上模擬數十年之後，並在模擬中測試政策。失敗在於：儘管精密，它仍是由一群專家建立的單一量化模型，他們選擇的邊界和數字都被烤死在裡面。它無法同時容納多個互相衝突的世界觀，它的預測引起激烈爭議，而且它把人當成機械式的變數——沒有能動性、沒有詮釋、沒有政治。

- How it worked: write stocks, flows, and delayed feedback loops as equations, simulate decades ahead on a computer, and test policies inside the simulation.

  運作方式：把存量、流量與帶延遲的迴饋迴圈寫成方程式，在電腦上模擬數十年之後，並在模擬中測試政策。

- What it gave us: a visible explanation of why obvious policies backfire later, made famous by The Limits to Growth in 1972.

  留給我們什麼：對「為什麼顯而易見的政策日後會適得其反」的可見解釋，由 1972 年的《成長的極限》推廣開來。

- Where it broke down: still one quantitative model built by one group, with their boundaries and numbers baked in; it cannot hold conflicting worldviews and treats people as mechanical variables.

  何處失效：仍是由一群人建立的單一量化模型，邊界與數字烤死在裡面；它無法容納衝突的世界觀，並把人當成機械式變數。

#### The Viable System Model (1970s) — 可行系統模型（1970 年代）

Stafford Beer applied cybernetics to organizations. His claim: any system that survives must do five things. It must do the actual work, coordinate its parts, manage day-to-day operations, look outward and adapt, and hold a coherent identity and purpose. These five functions recur at every level of an organization, and each level must have enough variety to cope with the variety it faces. Beer took this to its extreme in Project Cybersyn, a real-time computer system meant to manage Chile's national economy from 1971 to 1973, which died with the coup. The model fails because it is prescriptive and top-down: it assumes the organization has one coherent purpose, when in reality purpose is contested, and it says nothing about negotiating meaning or handling power.

比爾把控制論應用到組織上。他的主張：任何能存活的系統必須做五件事。它必須做實際的工作、協調各部件、管理日常營運、向外看並調適，以及維持一致的身分與目的。這五項功能在組織的每個層次都一再出現，而每個層次都必須有足夠的多樣性來應付它面對的多樣性。比爾在 Cybersyn 計畫中把這一點推到極致——一套旨在 1971 至 1973 年間管理智利全國經濟的即時電腦系統，它隨著政變而消亡。這個模型失敗，因為它是規範性的、由上而下的：它假設組織有一個一致的目的，但現實中目的是被爭奪的，而且它對協商意義或處理權力隻字未提。

- How it worked: check an organization against five functions every surviving system must have (the work, coordination, day-to-day management, outward adaptation, and identity), repeated at every level.

  運作方式：用每個存活系統都必須具備的五項功能來檢核一個組織（工作、協調、日常管理、向外調適、身分），在每個層次重複。

- What it gave us: a way to diagnose whether an organization can survive in a turbulent world, pushed to the limit by Project Cybersyn in Chile, 1971 to 1973.

  留給我們什麼：一種診斷組織能否在動盪世界中存活的方法，並在 1971 至 1973 年智利的 Cybersyn 計畫中被推到極致。

- Where it broke down: prescriptive and top-down; it assumed one coherent purpose and said nothing about negotiating meaning or handling power.

  何處失效：規範性且由上而下；它假設單一一致的目的，對協商意義與處理權力隻字未提。

### The soft turn: 1970s to 1990s — 軟性轉向：1970 到 1990 年代

#### Wicked problems (1973) — 棘手問題（1973）

The design theorists Horst Rittel and Melvin Webber named the class of problem that rational planning cannot solve: wicked problems. A wicked problem has no definitive formulation, no stopping rule, and no true-or-false test of a solution, only better or worse. Solutions are one-shot, because you cannot experiment on a society and then undo it. Every wicked problem is essentially unique, and every attempt to solve one changes the problem itself. Their conclusion was that such problems call for argument and participation rather than calculation, which is why Rittel later built Issue-Based Information Systems to map the issues and arguments in a debate. It is a diagnosis rather than a method, and that is exactly why it shaped everything that came after instead of ending the search.

設計理論家里特爾與韋伯為理性規劃無法解決的那類問題命名：棘手問題。一個棘手問題沒有明確的表述、沒有停止規則、沒有對解的真假檢驗——只有較好或較壞。解是一次性的，因為你不能對一個社會做實驗然後復原它。每個棘手問題本質上都是獨一無二的，而每次試圖解決它都會改變問題本身。他們的結論是：這類問題需要的是論辯與參與，而不是計算——這就是為什麼里特爾後來建立了議題導向資訊系統，把一場辯論中的議題與論點畫成地圖。與其說它是方法，不如說它是診斷，而正因如此，它塑造了之後的一切，而不是終結了這場探索。

- How it worked: not a procedure but a diagnosis; it listed what makes a problem wicked: no definitive formulation, no stopping rule, no true-or-false test, one-shot solutions, essential uniqueness, and solutions that change the problem itself.

  運作方式：不是程序而是診斷；它列出是什麼讓問題變得棘手：沒有明確表述、沒有停止規則、沒有真假檢驗、解是一次性的、本質上獨一無二、而且解會改變問題本身。

- What it gave us: a name for the class of problem technical planning cannot touch, and the call for argument and participation instead of calculation.

  留給我們什麼：為技術規劃碰不了的那類問題命名，以及「以論辯與參與代替計算」的呼籲。

- Where it broke down: it prescribes no procedure itself, so it shaped the participatory and design traditions that followed rather than solving anything directly.

  何處失效：它本身不開出任何程序，因此它塑造了後續的參與式與設計傳統，而不是直接解決任何問題。

#### Soft systems methodology (1970s to 1980s) — 軟系統方法論（1970 到 1980 年代）

Peter Checkland answered after watching hard systems engineering fail again and again on messy management problems. The process: draw a rich picture of the mess, the players, and the conflicts. For each important viewpoint, write a root definition of the relevant system and check it with the CATWOE questions: who benefits, who does the work, what transformation is involved, what worldview is assumed, who owns it, what the environment constrains. Then build a conceptual model of what that system would do, compare it with reality, and use the differences to drive a debate toward an accommodation people can live with. The core idea is that systems are mental constructs, not objective facts, and different people legitimately construct them differently. The failure: it sets power aside. It assumes the stakeholders can be identified, are willing to take part, and are roughly equal, so the accommodation it reaches can paper over the fact that some parties dominate others. It is also slow, and it tends to produce learning and talk rather than decisions and action.

切克蘭德在目睹硬性系統工程在混亂的管理問題上一再失敗之後給出回應。流程是：為這團混亂、各方角色和衝突畫一張豐富圖。對每個重要的觀點，寫下相關系統的根本定義，並用 CATWOE 問題來檢核：誰受益、誰做事、涉及什麼轉換、假設了什麼世界觀、誰擁有它、環境施加什麼限制。然後建立一個概念模型，描述那個系統會做什麼，與現實比較，並用差異推動一場辯論，走向一個大家都能接受的安排。核心觀念是：系統是心智的建構，不是客觀的事實，而不同的人有正當性把它們建構得不一樣。失敗在於：它把權力擱在一旁。它假設利害關係人可以被辨識、願意參與、而且大致平等，因此它達成的「安排」可能只是掩蓋了某些一方支配另一方的事實。它也很慢，而且往往產生學習與對話，而不是決策與行動。

- How it worked: draw a rich picture of the mess, write a root definition for each viewpoint and check it with the CATWOE questions, build conceptual models, compare them with reality, and debate toward an accommodation.

  運作方式：為混亂畫一張豐富圖、為每個觀點寫根本定義並用 CATWOE 檢核、建立概念模型、與現實比較、辯論走向一個大家能接受的安排。

- What it gave us: a structured way to surface competing worldviews and find enough common ground to act, on the idea that systems are mental constructs, not objective facts.

  留給我們什麼：一套結構化的方式，讓互相競爭的世界觀現身，並找到足以行動的共同基礎——基於「系統是心智建構而非客觀事實」的觀念。

- Where it broke down: it set power aside, assumed the stakeholders are identifiable, willing, and roughly equal, and tended to produce learning and talk more than decisions and action.

  何處失效：它把權力擱在一旁，假設利害關係人可辨識、願意、大致平等，而且往往產生學習與對話多於決策與行動。

#### Critical systems thinking (1980s to 1990s) — 批判系統思維（1980 到 1990 年代）

Michael Jackson and Robert Flood answered that blind spot. Their method classifies the situation first: are the people involved unitary, sharing goals; pluralist, differing but reconcilable; or coercive, in genuine conflict with some oppressing others? Then it points to the matching method: hard methods for unitary situations, soft methods for pluralist ones, critical methods for coercive ones, and it demands that power be named and confronted rather than merely accommodated. The failure: it is a framework for choosing frameworks, heavy and abstract to apply, and its critique of power diagnoses more than it operates.

傑克遜與弗勒德回應了這個盲點。他們的方法先對情境分類：涉及的人是統一的（目標一致）、多元的（意見不同但可調和），還是強制的（真正衝突，某些人壓迫其他人）？然後它指出相配的方法：統一情境用硬性方法、多元情境用軟性方法、強制情境用批判方法，而且它要求權力被指名與面對，而不只是被遷就。失敗在於：它是一個用來選擇框架的框架，套用起來沉重而抽象，而它對權力的批判，診斷多於操作。

- How it worked: classify the situation first (unitary, pluralist, or coercive), then deliberately choose the method that fits and confront power directly.

  運作方式：先分類情境（統一、多元或強制），再刻意選擇相配的方法，並直接面對權力。

- What it gave us: methodological pluralism, choosing the right tool for the situation instead of defending one favorite, plus an explicit reckoning with domination.

  留給我們什麼：方法論多元主義——為情境挑對的工具，而不是捍衛某個偏愛——外加對支配關係的正視。

- Where it broke down: a framework for choosing frameworks, heavy and abstract to apply, and more diagnosis than a working procedure.

  何處失效：一個用來選擇框架的框架，套用起來沉重而抽象，診斷多於可操作的程序。

#### Actor-network theory (1980s) — 行動者網絡理論（1980 年代）

Latour, Callon, and Law grew it out of the sociology of science. Its method is to follow the actors and describe what they do, treating people and non-people symmetrically: a microscope, a sample, a grant, and a speed bump all count as participants. It traces how networks form and hold together through translation, inscription, and black-boxing, the point where a hard-won fact or a complex machine becomes an unquestioned object. The failure: it is descriptive, not prescriptive. It shows how a network holds together, but gives no basis for judging whether it should, and no operational way to change it.

拉圖、卡龍與勞從科學社會學中把它發展出來。它的方法是跟隨行動者、描述他們做了什麼，對人與非人一視同仁：一台顯微鏡、一份樣本、一筆經費、一個減速丘，都算參與者。它追蹤網絡如何透過轉譯、銘寫與黑箱化形成並維繫——黑箱化就是那個得來不易的事實或複雜的機器變成一個毋庸置疑的物件的時刻。失敗在於：它是描述性的，不是規範性的。它展示一個網絡如何維繫，卻沒有提供判斷它應不應該維繫的依據，也沒有可操作的改變方式。

- How it worked: follow the actors and describe what they do, treating people and non-people symmetrically, then trace translation, inscription, and black-boxing.

  運作方式：跟隨行動者、描述他們做了什麼，對人與非人一視同仁，然後追蹤轉譯、銘寫與黑箱化。

- What it gave us: a vivid account of how facts and technologies come to hold together as networks of people, instruments, materials, and institutions.

  留給我們什麼：對「事實與技術如何作為人、儀器、材料與制度的網絡而維繫在一起」的生動描述。

- Where it broke down: descriptive rather than prescriptive; it offers no way to judge whether a network is good and no operational way to change one.

  何處失效：描述性而非規範性；它不提供判斷一個網絡好不好的方式，也沒有可操作的改變方式。

### The complexity turn and today: 1980s onward — 複雜性轉向與今日：1980 年代起

#### Complexity science and the Santa Fe Institute (1984) — 複雜性科學與聖塔菲研究院（1984）

The Santa Fe Institute is where it took shape: it gathered physicists, biologists, economists, and computer scientists after noticing that ant colonies, economies, immune systems, ecosystems, brains, and stock markets all behave alike: many parts interacting locally, no central controller, and yet ordered, adaptive behavior *emerges*. Its tools include agent-based models, where simple rules for many agents produce a pattern nobody programmed; fitness landscapes, which show why adaptation gets trapped on mediocre peaks; self-organized criticality, the sandpile that avalanches from one added grain; and cellular automata, where a few local rules generate enormous complexity. The failure: much of it stayed in toy models far from any real city or economy, and it stands outside the system simulating it. It explains why prediction and central planning fail, but gives a person inside the system no method for acting.

聖塔菲研究院是它成形的地方：它聚集了物理學家、生物學家、經濟學家和電腦科學家，因為人們注意到蟻群、經濟體、免疫系統、生態系、大腦和股市的行為如出一轍：許多部件在局部互動、沒有中央控制者，然而有序的、調適性的行為卻「湧現」出來。它的工具包括代理人模型——許多代理人遵循簡單規則，產生出沒有人程式設計過的圖樣；適應度景觀——解釋為什麼調適會被困在平庸的高峰上；自組織臨界性——多加一粒沙就引發雪崩的沙堆；以及細胞自動機——幾條局部規則產生巨大的複雜性。失敗在於：其中許多停留在遠離任何真實城市或經濟體的玩具模型上，而且它是站在系統外面模擬它。它解釋了為什麼預測與中央計畫會失敗，卻沒有給系統內部的人任何行動的方法。

- How it worked: write simple local rules for many agents and simulate them on a computer, letting the global pattern emerge; alongside fitness landscapes, self-organized criticality, and cellular automata.

  運作方式：為許多代理人寫下簡單的局部規則，在電腦上模擬它們，讓整體圖樣自行湧現；並配合適應度景觀、自組織臨界性與細胞自動機。

- What it gave us: a genuine explanation of how order, adaptation, and novelty arise with no one in charge, and of why prediction and central planning fail.

  留給我們什麼：對「秩序、調適與新奇如何在無人掌舵下產生」的真正解釋，以及對「預測與中央計畫為何失敗」的解釋。

- Where it broke down: much of it stayed in toy models far from real economies and cities, and its outside, simulating stance gives someone inside the system no way to act.

  何處失效：其中許多停留在遠離真實經濟與城市的玩具模型上，而它置身系統之外模擬的立場，沒有給系統內的人任何行動方式。

#### Network science (1998 to 1999) — 網絡科學（1998 到 1999 年）

Watts and Strogatz, and Barabási and Albert, produced it. Two findings shaped everything after: small-world networks, where a few long-range links make any two nodes a handful of steps apart; and scale-free networks, where a few hubs carry most of the connections, making the network tough against random failure but fragile against a targeted attack on the hubs. This became the standard language for cascading failure and systemic risk, with the 2008 financial crisis read as a contagion across a densely connected banking network.

它由瓦茨與斯托加茨、以及巴拉巴西與艾伯特提出。兩項發現塑造了之後的一切：小世界網絡——幾條長程連結讓任意兩個節點只隔幾步之遙；以及無尺度網絡——少數樞紐承載了大部分連結，使網絡對隨機故障很強韌、對針對樞紐的定向攻擊卻很脆弱。這成為級聯失效與系統性風險的標準語言，2008 年金融危機就被解讀為在一張高度連結的銀行網絡上蔓延的傳染。

- How it worked: model a system as nodes and links, then measure the shape of the connections.

  運作方式：把系統建模為節點與連結，然後量測連結的形狀。

- What it gave us: the small-world and scale-free findings, showing why real networks survive random failure but shatter under a targeted attack on their hubs, and the standard language for cascades and systemic risk.

  留給我們什麼：小世界與無尺度兩項發現，說明為什麼真實網絡能熬過隨機故障、卻在樞紐遭到定向攻擊時碎裂，以及級聯與系統性風險的標準語言。

- Where it broke down: it captures structure only, saying nothing about meaning, agency, or purpose, and its predictions on messy real systems are limited.

  何處失效：它只捕捉結構，對意義、能動性或目的隻字未提，而且它對混亂的真實系統的預測能力有限。

#### Resilience and panarchy (1973 to 2002) — 韌性與泛體制（1973 到 2002 年）

The tradition describes how ecosystems and coupled human-natural systems persist through shocks. The adaptive cycle runs through growth, then conservation, where the system becomes efficient but rigid and fragile, then release when a disturbance breaks it, then reorganization, where something new can emerge. Panarchy nests these cycles across scales, so a collapse at a large, slow scale can cascade down. Adaptive management treats every policy as an experiment: act, monitor, adjust. The failure: it is diagnostic more than prescriptive, the question "resilience of what, for whom" is deeply political, and the thresholds where systems flip are hard to measure in practice.

這套傳統描述生態系與人為—自然耦合系統如何在衝擊中存續。調適性循環經歷成長、然後是保存——系統變得有效率卻僵硬而脆弱、然後是釋放——擾動把它打破、然後是重組——新的東西可以在這裡湧現。泛體制把這些循環跨尺度地嵌套起來，因此大尺度、慢速的崩解可以向下級聯。調適性管理把每項政策都當成一項實驗：行動、監測、調整。失敗在於：它診斷多於規範，「對什麼東西的韌性、為了誰」這個問題具有深刻的政治性，而系統翻轉的閾值在實務上難以量測。

- How it worked: describe the adaptive cycle (growth, conservation, release, reorganization), nest the cycles across scales in panarchy, and treat every policy as an experiment: act, monitor, adjust.

  運作方式：描述調適性循環（成長、保存、釋放、重組），在泛體制中把循環跨尺度嵌套，並把每項政策當成實驗：行動、監測、調整。

- What it gave us: an account of how ecosystems and coupled human-nature systems persist through shocks, adapt, and sometimes transform, plus a practical management stance.

  留給我們什麼：對生態系與人為—自然耦合系統如何在衝擊中存續、調適、有時轉變的說明，外加一種務實的管理立場。

- Where it broke down: diagnostic more than prescriptive; the question "resilience of what, for whom" is deeply political, and the thresholds where systems flip are hard to measure in practice.

  何處失效：診斷多於規範；「對什麼的韌性、為了誰」具有深刻的政治性，系統翻轉的閾值在實務上難以量測。

#### Cynefin (1999 to 2007) — Cynefin 框架（1999 到 2007 年）

Developed by Dave Snowden and published widely in 2007, it turned the whole history into a decision rule. It sorts situations into five domains. In clear situations, cause and effect are obvious, so apply the known best practice. In complicated ones, cause and effect are knowable through analysis, so get expert advice. In complex ones, cause and effect appear only in hindsight, so run small safe-to-fail experiments, watch, and amplify what works. In chaotic ones, no cause and effect is visible, so act first to stabilize, then reassess. The fifth domain, confusion, just means you do not yet know which of the others you are in. The central rule: never apply one domain's method in another. The weakness: it is under-specified, hard to test, and often misused as a rigid set of boxes. But its core insight is the lesson of the whole history: treating a complex problem as if it were merely complicated is the root of most failures.

由斯諾登開發、2007 年廣泛發表，它把整段歷史化成一條決策規則。它把情境分成五個域。在清晰的情境中，因果關係顯而易見，所以套用已知的最佳實踐。在繁複的情境中，因果關係可以透過分析得知，所以請教專家。在複雜的情境中，因果關係只有事後才看得出來，所以做小規模、安全失敗的實驗、觀察、放大有效的事物。在混亂的情境中，看不到任何因果關係，所以先行動穩住局面，再重新評估。第五個域「混惑」只是說你還不知道自己身處其他四個域中的哪一個。核心規則：絕不要把一個域的方法用在另一個域上。弱點是：它的規格不足、難以檢驗，而且常被誤用成一套僵化的格子。但它的核心洞見正是整段歷史的教訓：把一個複雜問題當成只是繁複來對待，是大多數失敗的根源。

- How it worked: sort the situation into clear, complicated, complex, chaotic, or simply confusing, then act the way that domain demands.

  運作方式：把情境分類為清晰、繁複、複雜、混亂或純粹令人困惑，然後以該域要求的方式行動。

- What it gave us: a simple decision rule that turns the whole history into everyday practice: match your stance to the situation, and never apply one domain's methods in another.

  留給我們什麼：一條簡單的決策規則，把整段歷史變成日常實踐：讓你的立場與情境相配，絕不要把一個域的方法用在另一個域。

- Where it broke down: under-specified, hard to test, and often misused as a rigid set of boxes.

  何處失效：規格不足、難以檢驗，常被誤用成僵化的格子。

#### Today: 2010s onward — 今日：2010 年代起

There has been no new grand method since roughly 2010, and that is deliberate. The field did three things at once. It grew honest about prediction: every model is a simplified story, so use several models and compare where they agree and disagree, as happened publicly during COVID, and use tools that work under deep uncertainty, such as robust decision making, which searches for options that avoid disaster across thousands of possible futures, and adaptive policy pathways, which commit only to the next step and switch course as monitoring shows which future is unfolding. It married complexity to data and computation: machine learning finds patterns in systems too tangled for hand-built models; recommender feeds and search rankings are themselves complex systems shaping attention and opinion; digital twins let operators test changes on a live copy of a real system; and large language models are now both complex systems in their own right and tools for reasoning about other complex systems. And it turned from describing systems to deliberately changing them: the causal inference revolution, through Judea Pearl's causal diagrams and the 2021 Nobel work of Card, Angrist, and Imbens, proved that you can learn real causal facts even in a tangled world, while also teaching that evidence is not portable, since a result that holds in one place often fails in another. Complexity economics measures what a country can make and predicts its growth from that. Transition theory and mission-oriented policy, including Amsterdam's adoption of doughnut economics in 2020, set bold directions and shape markets toward them. Climate science gave complexity its highest-stakes application through planetary boundaries and tipping points, thresholds that can flip irreversibly and cascade. And the 2020s vocabulary of polycrisis names what happens when pandemic, war, inflation, energy, food, and climate fail together and worsen each other. COVID was the live stress test: prediction failed, several models had to be compared, and policies had to be probed and adapted in real time.

大約從 2010 年起就沒有新的宏大方法，而這是刻意的。這個領域同時做了三件事。它對預測變得誠實：每個模型都是一個簡化的故事，所以要用好幾個模型、比較它們在哪裡一致、在哪裡分歧——COVID 期間就公開這樣做過——並使用在深度不確定性下仍然有效的工具，例如穩健決策：在成千上萬個可能的未來中搜尋能避開災難的選項；以及調適性政策路徑：只承諾下一步，並隨著監測顯示哪個未來正在展開而轉換路線。它把複雜性與資料、運算結了婚：機器學習在手動建模理不出頭緒的系統中找出圖樣；推薦動態與搜尋排名本身就是塑造注意力與意見的複雜系統；數位分身讓營運者在真實系統的即時副本上測試變更；而大型語言模型如今既是自身就成立的複雜系統，也是對其他複雜系統進行推理的工具。它還從描述系統轉向刻意改變系統：因果推論革命——透過珀爾的因果圖，以及卡德、安格里斯特與因本斯 2021 年的諾貝爾獎成果——證明了即使在糾纏不清的世界中也能學到真實的因果事實，同時也教導我們：證據不能隨意移植，因為在一個地方成立的結果，往往在另一個地方失效。複雜性經濟學量測一個國家能生產什麼，並從中預測它的成長。轉型理論與使命導向政策——包括阿姆斯特丹在 2020 年採納甜甜圈經濟學——設定大膽的方向，並把市場塑造成朝它們前進。氣候科學透過行星邊界與臨界點——可能不可逆翻轉並級聯的閾值——給了複雜性最高風險的應用場景。而 2020 年代的「複合危機」一詞，為疫情、戰爭、通膨、能源、糧食與氣候同時失效、並相互加劇的情況命名。COVID 是一場實彈壓力測試：預測失靈、必須比較多個模型、政策必須在即時中被試探與調適。

- How it worked: use several models at once and compare where they agree and disagree, use decision tools that work without prediction, and aim the tools at changing systems rather than only describing them.

  運作方式：同時使用多個模型並比較它們的異同、使用不依賴預測的決策工具、把工具瞄準改變系統而不只是描述系統。

- What it gave us: robust decision making, adaptive policy pathways, causal inference, digital twins, transition and mission-oriented policy, and the science of tipping points and polycrisis.

  留給我們什麼：穩健決策、調適性政策路徑、因果推論、數位分身、轉型與使命導向政策，以及臨界點與複合危機的科學。

- Where it still falls short: it is young and unsettled, the polycrisis vocabulary is journalistic rather than rigorous, and none of it removes the need to match the approach to the situation.

  目前仍有不足：它年輕而未定型，複合危機的詞彙是新聞式的而非嚴謹的，而且這一切都沒有消除「讓方法與情境相配」的必要。

The through-line of all of it: every method failed by freezing one thing that a complex system refuses to hold still. Operations research froze the objective. System dynamics froze the model. The Viable System Model froze the purpose. Soft systems methodology froze the list of stakeholders. Actor-network theory froze the network. Every lens is also a blind spot, which is what Ashby's law predicts: your approach needs at least as much variety as the problem, and no single method has enough. So the endpoint of the whole story is pluralism: match tools to situations and combine them.

貫穿一切的主線是：每種方法都因為把某樣複雜系統拒絕靜止不動的東西凍結住而失敗。作業研究凍結了目標。系統動力學凍結了模型。可行系統模型凍結了目的。軟系統方法論凍結了利害關係人的名單。行動者網絡理論凍結了網絡。每個鏡片同時也是盲點——這正是阿什比法則所預測的：你的方法需要至少和問題一樣多的多樣性，而沒有任何單一方法擁有足夠的多樣性。所以整段故事的終點是多元主義：讓工具與情境相配，並把它們組合起來。

## 3. Working with problems you cannot solve — 與你無法解決的問題共處

So if there is no winning method, what do you do on Monday morning? Asking for the one best method is itself the trap that sank every era above. But there is a best way of working, and it is a loop rather than a method. Each step below comes from a specific failure in the last section.

那麼，如果沒有必勝的方法，星期一早上你該怎麼做？尋求那唯一最好的方法，本身就是沉沒了上述每個時代的陷阱。但確實有一種最好的工作方式，而它是一個迴圈，不是一種方法。以下每個步驟都來自上一節中的某個具體失敗。

1. Diagnose before you act. First ask what kind of problem this is: clear, complicated, complex, chaotic, or wicked. Getting this diagnosis wrong is the mistake behind most of the failures above. The diagnosis itself costs almost nothing and decides everything that follows.

   行動之前先診斷。先問這是哪一種問題：清晰、繁複、複雜、混亂，還是棘手。把這個診斷搞錯，是上述大多數失敗背後的錯誤。診斷本身幾乎不花成本，卻決定後續的一切。

2. Frame the problem together with the people inside it. Surface the competing views and make the assumptions explicit before building a shared-enough picture of the situation. Hard methods are only as good as the framing underneath them.

   和身處問題中的人一起框定問題。讓互相競爭的觀點現身、把假設說明白，然後再建立一幅足夠共享的情境圖像。硬性方法的好壞，取決於底下的框定。

3. Respect the power in the room. Ask who benefits and who bears the cost. Do not pretend consensus is always possible; an "accommodation" can simply ratify whoever was already strongest.

   尊重房間裡的權力。問誰受益、誰承擔成本。不要假裝共識總是可能的；一個「安排」可能只是在追認原本最強勢的一方。

4. Combine tools instead of worshipping one. Use optimization on the genuinely tractable parts, soft structuring on the contested parts, critical analysis on the coercive parts, and probing on the emergent parts.

   組合工具，而不是崇拜單一工具。在真正可處理的部分用最佳化、在有爭議的部分用軟性結構化、在強制的部分用批判分析、在湧現的部分用試探。

5. Act in small, reversible steps, then watch what happens. Probe, sense, respond: run safe-to-fail experiments, amplify what works, dampen what does not. When you cannot even assign probabilities to the future, use options that stay acceptable across many possible futures, and plans that commit only to the next step.

   以小而可逆的步驟行動，然後觀察發生什麼。試探、感知、回應：做安全失敗的實驗、放大有效的、抑制無效的。當你甚至無法為未來賦予機率時，使用在許多可能的未來中都仍然可接受的選項，以及只承諾下一步的計畫。

6. Build the system's ability to absorb surprise. A system tuned for maximum efficiency is brittle, because the tuning removed the slack that would absorb a shock. Keep some redundancy, diversity, and modularity on purpose, and watch for the moment a system has grown so rigid that a small disturbance could break it.

   建立系統吸收意外的能力。一個被調校到最高效率的系統是脆的，因為調校移除了原本能吸收衝擊的餘裕。刻意保留一些冗餘、多樣性與模組化，並留意系統變得僵硬到一點小擾動就可能讓它斷裂的時刻。

7. Push where the system will carry you, rather than trying to control the whole. There is no single lever. Look for hubs in a network, or niches where a new approach can grow until the surrounding regime gives way. Set a direction and shape the conditions instead of micromanaging every part.

   在系統會載著你前進的地方施力，而不是試圖控制整體。沒有單一的槓桿。尋找網絡中的樞紐，或讓新方法得以成長、直到周邊體制讓位的生態位。設定方向、塑造條件，而不是對每個部件微觀管理。

8. Learn continuously, but treat evidence as local. Measure what happens and adjust. A result that worked in one place and time may fail here, because the surrounding system differs, so scaling a proven fix is itself a complex problem, not a copy-and-paste job.

   持續學習，但把證據視為地方性的。量測發生了什麼並調整。在某個時間地點有效的結果可能在此地失效，因為周圍的系統不同，所以把一個已驗證的修補放大施行，本身就是一個複雜問題，不是複製貼上的工作。

9. Accept that you can steer, never solve. At the top rung there is no finish line, and every fix changes the problem. Aim for provisional, good-enough action that the people involved agree on, and keep adjusting.

   接受你只能引導，永遠無法解決。在最上一階沒有終點線，而每次修補都會改變問題。瞄準那些暫時性的、夠好的、相關人士都同意的行動，並持續調整。

The whole loop in one sentence: know what kind of problem you are facing, frame it with the people inside it, respect the power, combine the right tools, act small and reversible, watch and adapt, build in the ability to absorb surprise, push where the system amplifies you, learn without over-trusting, and accept that you steer rather than solve.

用一句話說完整個迴圈：知道自己面對的是哪一種問題、和身處其中的人一起框定它、尊重權力、組合對的工具、以小而可逆的方式行動、觀察並調適、內建吸收意外的能力、在系統會放大你的地方施力、學習但不過度信任，並接受你是引導而非解決。

That brings us back to where we started. Complexity is a different kind of thing from complicated, and the ladder in section 1 is still the best map we have. The reliable way to meet it is to stay curious, keep your steps small enough to reverse, and keep checking whether the world answered back the way you expected. The moment you believe you have found the one method that finally cracks complexity is the moment you have stopped doing any of that.

這把我們帶回起點。複雜與繁複是不同種類的東西，而第 1 節的那把階梯仍然是我們最好的地圖。面對它的可靠方式是：保持好奇、讓你的步驟小到可以回頭、並且不斷檢查世界的回應是否如你所預期。當你相信自己終於找到了破解複雜性的那種方法的那一刻，就是你停止做上述一切的那一刻。

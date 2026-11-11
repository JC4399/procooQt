# Systems, explained simply — 系統，簡單說明

Most of what you use every day is a system, even if nobody calls it that. This guide gives you a basic vocabulary for looking at anything, from a toaster to a company to your own body, and asking three questions: what are the parts, how do they connect, and what does the whole do? No technical background is needed.

你每天使用的東西大多是一個系統，即使沒有人這樣稱呼它。這份指南給你一套基礎詞彙，讓你看待任何事物——從烤麵包機、到公司、再到你自己的身體——都能問三個問題：部件有哪些、它們如何連結、整體能做什麼？不需要任何技術背景。

## 1. A function and a system — 函式與系統

Start with the smaller idea: a function. A function is a named, reusable block that does one specific job. Every function has three parts: an input (the information it receives), the work (the steps it performs), and an output (the result it gives back). A function can also have a side effect, which means it changes something outside itself, like saving a file or printing to a screen, instead of only returning a value.

先從較小的概念開始：函式。函式是一個有名字、可重複使用的區塊，專門做一件特定的工作。每個函式都有三個部分：輸入（它接收的資訊）、工作（它執行的步驟），以及輸出（它回傳的結果）。函式還可以有副作用，也就是它會改變自身以外的東西，例如存檔或在螢幕上列印，而不只是回傳一個值。

Take a toaster. The input is bread plus a press of the toast button. The work is heating the bread. The output is toasted bread, and the side effect is that the room now smells like toast. In math, a function is even simpler: a rule that turns one number into another, like f(x) = 2x. Put in 3 and you get out 6. The same input always gives the same output.

以烤麵包機為例。輸入是麵包加上按下烤麵包按鈕的動作，工作是把麵包加熱，輸出是烤好的麵包，而副作用是房間現在聞起來有烤麵包的味道。在數學裡，函式更簡單：一條把一個數字變成另一個數字的規則，例如 f(x) = 2x。放進 3，就得到 6。相同的輸入永遠給出相同的輸出。

A system is bigger: a set of things that are connected and work together to do something no single thing can do alone. Three ideas make up a system:

系統則更大：一組彼此連結、共同合作的事物，能做到任何單一事物獨力無法做到的事。三個概念構成一個系統：

- Parts: a system is made of smaller pieces, each with its own role.

  部件：系統由更小的零件組成，每個零件都有自己的角色。

- Connections: the parts interact, passing things back and forth.

  連結：零件彼此互動，來回傳遞東西。

- Whole: when the parts work together, the system behaves in a way that is more than the sum of its parts. This extra behavior is called *emergence*. In something built, like a car, that behavior is designed on purpose and can be tested. In something alive, like a flock of birds turning as one, it happens by itself and cannot be fully predicted.

  整體：當零件共同合作時，系統的行為會大於各部分的總和。這種額外的行為稱為「湧現」。在人造物（例如汽車）中，這種行為是刻意設計出來的，也可以被測試；在活的東西（例如一群同步轉向的鳥）中，它會自行發生，而且無法被完全預測。

A bicycle makes this concrete. The wheels, chain, pedals, and frame are the parts. They are connected: the pedals turn the chain, the chain turns the wheel. Together they let you travel, and no single part can do that alone. Your body is another example. Heart, lungs, brain, and muscles are parts, connected by blood vessels and nerves, and together they keep you alive.

自行車讓這個概念變得具體。輪子、鏈條、踏板和車架就是部件。它們彼此連結：踏板帶動鏈條，鏈條帶動輪子。它們一起讓你能夠移動，而任何單一部件都無法獨自做到這件事。你的身體是另一個例子。心臟、肺、大腦和肌肉是部件，由血管和神經連結起來，共同讓你活著。

A system also has a *boundary*: an edge that separates what is inside the system from what is outside. For a bicycle, the boundary is the surface of the metal and rubber. For your body, it is your skin.

系統還有一條「邊界」：一道把系統之內與系統之外分開的邊緣。對自行車來說，邊界是金屬和橡膠的表面；對你的身體來說，邊界是你的皮膚。

Now the two ideas connect. A function is the smallest unit of doing one thing. A system is what you get when many functions, plus the parts that hold them, are wired together. Functions are the building blocks; systems are the buildings. And this matters for what comes next: a whole system can act like a single function when you look at it from far enough away.

現在兩個概念接上了。函式是做一件事的最小單位；系統則是把許多函式、加上支撐它們的部件，全部串接起來之後得到的東西。函式是積木，系統是建築。這一點對接下來的內容很重要：只要離得夠遠，整個系統可以表現得像單一函式。

## 2. Abstraction and the black box — 抽象與黑箱

You can look at anything from many levels, and each level gives a valid, complete picture. It just answers a different question. Zoom in and you see more detail, answering how it works. Zoom out and you see the bigger picture, answering what it does.

你可以從許多層次看待任何事物，而每個層次都給出一幅有效、完整的圖像。它只是回答不同的問題。放大看，你看到更多細節，回答它是如何運作的。縮小看，你看到更大的全貌，回答它是做什麼的。

Take water. At the deepest level you see particles and the forces between them, which explains why molecules behave the way they do. One level up, molecules collide and move, which explains temperature. Higher still, water flows with pressure and waves, which explains how it moves through a pipe. At the everyday level, water is simply a glass you can drink. Each level is correct. None of them is more true; they are just different scopes.

以水為例。在最深的層次，你看到粒子和粒子之間的作用力，這解釋了分子為什麼有那樣的行為。往上一層，分子碰撞、移動，這解釋了溫度。再往上，水帶著壓力流動、形成波浪，這解釋了它如何在水管中流動。在日常層次，水就是一杯可以喝的東西。每個層次都是正確的。沒有一個比另一個更真實；它們只是不同的範圍。

Every level has a boundary, just like the system boundary from the first section. The boundary decides what is inside, the parts you examine closely at this level, and what is outside, everything you take as given at this level. At any level you only need to understand that level. You do not need to know about molecules to understand a pipe; what crosses the boundary, the input and output, is enough. That crossing point is the *interface*.

每個層次都有一條邊界，就像第一節的系統邊界一樣。邊界決定了什麼在之內——你在這個層次仔細檢視的部件——以及什麼在之外——你在這個層次視為理所當然的一切。在任何層次，你只需要理解那個層次。要理解水管，你不需要懂分子；跨越邊界的東西——輸入與輸出——就夠了。那個跨越點就是「介面」。

When you use a function, you only see its input and output, not what happens inside. A system is the same: from the outside it is a black box with an interface, from the inside it is a system of parts. A system at one layer can even be a single function, one black box, at the layer above. Think of your body. At the top level, the body is one box: food and oxygen go in, and being alive comes out. You do not think about cells. Zoom in one level and the body is a system of organs, each organ a black box with its own input and output. Zoom in again and each organ is a system of cells. Each layer hides the layer below it, and that hiding is what makes complex things understandable. You cannot hold every layer in your head at once, so you pick the layer that matches your question and trust the layers below.

當你使用一個函式時，你只看到它的輸入和輸出，看不到內部發生什麼。系統也一樣：從外面看，它是一個帶有介面的黑箱；從裡面看，它是一個由部件組成的系統。一個層次的系統，在上一個層次甚至可以是單一函式、單一黑箱。想想你的身體。在最上層，身體是一個箱子：食物和氧氣進去，活著出來。你不會想到細胞。放大一層，身體是一個由器官組成的系統，每個器官都是一個黑箱，有自己的輸入和輸出。再放大，每個器官是一個由細胞組成的系統。每一層都把它下面那一層隱藏起來，而這種隱藏正是讓複雜事物變得可理解的原因。你無法同時把所有層次都放在腦中，所以你挑一個與你的問題相符的層次，並信任它下面的各層。

How do you choose where to draw a boundary? A good one has three properties. First, the inside is self-contained: you can describe what happens inside without referring to the outside. Second, the outside is self-contained: you can use the inside from the outside without knowing its details. Third, the two sides can change independently: you can rewrite the inside and the outside still works, as long as the interface stays the same.

那麼，該怎麼決定邊界畫在哪裡？一條好的邊界有三個特性。第一，內部是自足的：你可以在不提及外部的情況下描述內部發生什麼。第二，外部是自足的：你可以在不了解細節的情況下，從外部使用內部。第三，兩邊可以獨立改變：只要介面維持不變，你可以重寫內部，而外部照常運作。

A bad boundary splits a bicycle into a left half and a right half. Those parts are meaningless on their own, because the chain crosses the middle and the wheels sit on both sides. A good boundary splits the bicycle into a wheel system and a frame system. Each has a clear job, and they connect at clear points like the axle and the seat post.

一條壞的邊界會把自行車切成左半邊和右半邊。這些部件本身沒有意義，因為鏈條橫跨中間，而輪子分佈在兩側。一條好的邊界把自行車分成輪子系統和車架系統。每個都有明確的工作，並在明確的點上連結，例如車軸和座管。

A function is the smallest boundary, a system is many functions inside a bigger boundary, and layers of abstraction are just nested boundaries. Zoom out and a system becomes one function in a bigger system. Zoom in and a function becomes a system of smaller functions.

函式是最小的邊界，系統是許多函式放在一條更大的邊界之內，而抽象層次就是一層層嵌套的邊界。縮小看，一個系統變成更大系統中的一個函式。放大看，一個函式變成由更小函式組成的系統。

One question is still open: when many boundaries sit inside one system, how are they arranged with each other?

還有一個問題懸而未決：當許多邊界同處於一個系統之中，它們彼此是如何排列的？

## 3. The shape of a system — 系統的形狀

A *structure* is the pattern of how parts are arranged and connected, a pattern of boundaries and the connections between them. Different shapes solve different problems:

「結構」是部件排列與連結的方式，是邊界與邊界之間連結的圖樣。不同的形狀解決不同的問題：

- Hierarchy (a tree). Branches spread downward from one root: one parent, many children, no loops. Its job is to organize and delegate: a big job gets split into smaller jobs, each with a clear owner. Your computer's folder system is one.

  階層（一棵樹）。枝幹從一個根向下展開：一個父節點、多個子節點、沒有迴圈。它的工作是組織與分派：一件大工作被拆成較小的工作，每件都有明確的負責人。你電腦的資料夾系統就是一例。

- Network (a web). Many points connected many-to-many, so there are multiple paths between any two points. Use it when surviving failure matters: if one route is blocked, another still works. The internet and subway maps are networks.

  網絡（一張網）。許多節點以多對多的方式連結，任意兩點之間都有多條路徑。當「在故障中存活」很重要時就用它：一條路被阻斷，另一條仍然可用。網際網路和地鐵路網都是網絡。

- Modular (blocks with standard plugs). Independent blocks that connect through fixed, standard ports, like LEGO or USB. Use it when parts need to be swappable. Train cars work this way: any car couples to any other car.

  模組化（帶標準插頭的積木）。獨立的方塊透過固定、標準的連接埠連結，例如樂高或 USB。當部件需要可以互換時就用它。火車車廂就是這樣運作的：任何車廂都能與任何其他車廂接駁。

- Flat (a circle of equals). All parts are equal, no center, no levels, and everyone connects directly to everyone. Use it for collaboration without a boss, like a potluck where everyone brings a dish and the meal happens even if one person does not show up.

  平坦（一圈對等者）。所有部件地位相等，沒有中心、沒有層級，每個人直接與每個人連結。用於沒有老闆的協作，例如百樂餐：每人帶一道菜，即使有一個人沒到，這頓飯仍然成立。

- Matrix (a grid). Rows cross columns, and every cell sits at the intersection of two groups. Use it to cross-reference two groups, like a hospital roster with doctors on the rows and days on the columns.

  矩陣（一個網格）。列與欄交叉，每個格子位於兩組的交點上。用於交叉對照兩組，例如醫院的值班表：列是醫生，欄是日期。

Why do systems come in so many shapes, and why is there no single universal shape? Because there is no universal job. Every job puts its own demands on the parts: who must talk to whom, how often, in what direction, and who decides when people disagree. Those demands are what shape the structure. Too many parts for one person to control and a hierarchy shows up, so each level handles what it can. Work that has to keep going even when something fails needs a network with backup paths. Parts that get swapped often need modular blocks with standard ports. Equal partners with nobody in charge give you a flat structure. A job that crosses two groups, like doctors and days, gives you a matrix. Some shapes simply will not fit a given job, and even among the ones that fit, people still choose, weighing trade-offs like speed against cost or control against flexibility. That is why no one shape is best for everything: each shape solves a different kind of job.

為什麼系統有這麼多種形狀？為什麼沒有單一萬用的形狀？因為沒有萬用的工作。每種工作都對部件提出自己的要求：誰必須和誰說話、多久一次、朝哪個方向，以及意見不合時由誰決定。這些要求塑造了結構。部件多到一個人控制不來，階層就出現了，讓每一層負責它管得動的部分。即使某處故障也必須繼續運作的工作，需要有備援路徑的網絡。經常被更換的部件，需要帶標準連接埠的模組化方塊。地位相等、沒有人掌舵的夥伴，得到的是平坦結構。橫跨兩組的工作——例如醫生和日期——給你矩陣。有些形狀就是不合某項工作；而在合適的形狀之中，人們仍然要做選擇，權衡取捨，例如速度對成本、控制對彈性。這就是為什麼沒有任何一種形狀在所有事情上都最好：每種形狀解決的是不同類型的工作。

A good shape matches the job's natural divisions. Parts that talk constantly belong close together in the structure; parts that rarely interact belong far apart; a part that must be independent gets a clean boundary with a standard interface. Match the shape to the job and the system runs smoothly. Get the shape wrong and you get friction: slow communication, confusion about who is responsible, things breaking whenever one part changes.

好的形狀與工作天然的分界相配。持續溝通的部件在結構中應該靠得很近；很少互動的部件應該離得遠；必須獨立的部件會得到一條乾淨的邊界和標準介面。讓形狀與工作相配，系統就運作順暢。形狀配錯，你就得到摩擦：溝通緩慢、責任歸屬混亂、任何一個部件一改就出問題。

All of this is about how a system is put together. How do you tell whether the finished thing is any good?

以上說的都是系統如何組裝起來。那要怎麼判斷完成的東西好不好？

## 4. What makes a system good — 什麼讓一個系統是好的

First, a system has to solve the problem at all, and keep solving it well. After that, people judge it on qualities like these:

首先，系統至少要能解決那個問題，而且持續解決得好。之後，人們會用以下這些品質來評判它：

| Quality | What it means |
|---|---|
| Works | It solves the problem it was built for |
| Reliable | The same good result every time |
| Efficient | No wasted time, money, energy, or effort |
| Simple | You can understand, use, and explain it in a few sentences |
| Maintainable | You can fix it when it breaks and update it when it needs to change |
| Adaptable | It handles new situations without being rebuilt from scratch |
| Scalable | It grows when demand grows |
| Safe | It does not harm people, data, the environment, or other systems it touches |
| Fast enough | Fast means different things for a heart surgery than for a tree |
| Worth the cost | What you get out is more than what you put in |

| 品質 | 意思 |
|---|---|
| 可用 | 它解決了它被打造來解決的問題 |
| 可靠 | 每次都得到同樣好的結果 |
| 有效率 | 不浪費時間、金錢、精力或心力 |
| 簡單 | 你能用幾句話理解、使用並解釋它 |
| 可維護 | 它壞了你能修，需要改變時你能更新 |
| 可適應 | 它能應付新情況，而不必從頭重建 |
| 可擴展 | 需求增長時它能跟著成長 |
| 安全 | 它不傷害人、資料、環境，或它接觸到的其他系統 |
| 夠快 | 「快」對心臟手術和對一棵樹有不同的意義 |
| 值得成本 | 你得到的多於你投入的 |

These qualities are about how well the system performs, which is separate from what it does. Engineers call them the "-ilities": reliability, availability, maintainability, safety, scalability, and so on. A system that does its job perfectly but crashes every hour is useless. A system that is fast but unsafe is dangerous. Which of these matter most depends on the job, and the shape you choose decides which of them you get. And none of them is fixed at launch: they play out over time, because a system itself changes as time passes.

這些品質關乎系統表現得多好，與它做什麼是兩回事。工程師把它們統稱為「……性」一族：可靠性、可用性、可維護性、安全性、可擴展性等等。一個把工作做得完美但每小時當機一次的系統毫無用處。一個很快但不安全的系統是危險的。哪些最重要取決於工作，而你選擇的形狀決定了你會得到其中哪些。而且它們沒有一項在上線時就定死了：它們隨著時間展現，因為系統本身也會隨時間改變。

## 5. The life and death of a system — 系統的生與死

A system exists in time as well as in space. Its full journey, from first idea to retirement, is called its *lifecycle*:

系統存在於時間之中，也存在於空間之中。它從最初的想法到退役的完整旅程，稱為「生命週期」：

| Phase | What happens |
|---|---|
| Concept | What problem are we solving, who needs this, and is it feasible at all |
| Requirements | What the system must do and be. These are the contract between the system and the world. Capture them by talking to the people involved, writing clear statements like "the system shall...", checking you got it right, and tracking changes, because requirements always change over time |
| Design | How it will work: the parts, the structure, the interfaces |
| Build | Making the actual parts |
| Integration | Putting the parts together so they work as one whole. This is where most projects break, because parts that work perfectly alone can fail when combined. Throw everything together at once and it is fast but failures are hard to trace; add parts one at a time and test as you go and it is slower but safer |
| Verification and validation | Two different questions. Verification asks, did we build the system right, meaning does it meet the requirements we wrote down. Validation asks, did we build the right system, meaning does it meet the real needs of the people who use it. You can pass the first and fail the second |
| Operation | Using the system in the real world |
| Maintenance | Fixing and updating it so it keeps working |
| Disposal | End of life: decommission it, recycle it, replace it |

| 階段 | 發生什麼 |
|---|---|
| 概念 | 我們在解決什麼問題、誰需要它、它到底可不可行 |
| 需求 | 系統必須做什麼、必須是什麼。這是系統與世界之間的契約。透過與相關的人談話來取得需求，寫下清楚的陳述如「系統應……」，檢查你有沒有寫對，並追蹤變更，因為需求總會隨時間改變 |
| 設計 | 它將如何運作：部件、結構、介面 |
| 建造 | 製作出真正的部件 |
| 整合 | 把部件組合起來，讓它們作為一個整體運作。大多數專案都在這裡出問題，因為單獨運作完美的部件，合在一起時可能失敗。一次全部丟在一起，速度快但故障難以追查；一次加一個部件、邊做邊測，速度慢但更安全 |
| 驗證與確認 | 兩個不同的問題。驗證問的是：我們把系統做對了嗎——它是否符合我們寫下的需求。確認問的是：我們做出的是正確的系統嗎——它是否符合使用者的真正需要。你可以通過第一關，卻過不了第二關 |
| 營運 | 在真實世界中使用系統 |
| 維護 | 修復與更新它，讓它持續運作 |
| 除役 | 生命終點：讓它退役、回收、或替換它 |

Each phase is also a layer of abstraction. Concept is zoomed all the way out, and build is zoomed far in. A common way to picture the journey is the V-model: down the left side from concept to build, across the bottom for integration, and up the right side through testing to operation.

每個階段也是一個抽象層次。概念是完全縮小看到的全貌，建造是放大到很深處。描繪這段旅程的常見方式是 V 模型：沿左邊從概念往下走到建造，橫跨底部是整合，再沿右邊向上經過測試到營運。

Put together, the lifecycle says this: a system is not a static object. It is born when someone has a problem worth solving, grows through design and build, lives while it operates and gets maintained, and dies when the problem changes or a better system replaces it. Dying is not always failure. A system that did its job for years and was retired cleanly lived a full life. And the early phases matter more than any others, because the boundaries you draw and the shape you pick in the first weeks follow the system for its whole life. They cost almost nothing to change on paper and a fortune to change once the parts exist. A system that merely launches is not the goal. A system that lasts is.

總結起來，生命週期說的是：系統不是一個靜止的物體。當某人遇到一個值得解決的問題時它誕生，透過設計與建造成長，在營運與維護中活著，當問題改變或更好的系統取代它時死去。死亡不一定是失敗。一個盡職多年、乾淨退役的系統，度過了完整的一生。而早期階段比其他任何階段都重要，因為你在頭幾週畫下的邊界和選定的形狀，會跟著系統一輩子。在紙上改動它們幾乎不花錢，等部件做出來再改就要花一大筆錢。僅僅上線不是目標。能長久運作才是。

Everything so far has been one general way of looking at systems. In practice, people have turned it into whole fields of study, and those fields do not all agree on what matters most.

到目前為止，以上都只是看待系統的一種通用方式。在實務中，人們把它發展成一整個又一整個的研究領域，而這些領域對於什麼最重要並不全都意見一致。

## 6. Three lenses on systems: OR, IE, and SE — 看系統的三副鏡片：OR、IE 與 SE

Systems thinking did not stay one abstract idea. It grew into whole fields of study, and the richest view of the topic comes from seeing how differently those fields look at the same system. Three of them matter most.

系統思維沒有停在一個抽象的想法上。它成長為一整個又一整個的研究領域，而對這個主題最豐富的視角，來自看見這些領域看待同一個系統的方式有多麼不同。其中三個最重要。

Operations research, or OR, asks: given the options, which decision is best? It treats a system as a mathematical model: variables to choose, one objective to maximize or minimize, and constraints that define what is allowed. In our vocabulary, the boundary is the set of allowed choices. OR's tools are linear programming, simulation, queuing theory, game theory, and shortest-path algorithms. It began in World War II, when the British military asked scientists where to place radar, how to route convoys, and how to hunt submarines, and after the war it moved into airlines, hospitals, and finance. Its well-known results include the simplex method for linear programming (Dantzig, 1947) and game theory (John Nash, Nobel Prize 1994). Everyday examples: GPS finding your shortest route, an airline scheduling thousands of crew and flights, a supermarket deciding how many checkout lanes to open. OR fits when you face a decision with many variables, you have data, and the goal is the optimal answer.

作業研究（OR）問的是：在這些選項中，哪個決策最好？它把系統當成一個數學模型：要選擇的變數、一個要最大化或最小化的目標，以及界定什麼被允許的約束。用我們的詞彙來說，邊界就是被允許的選項集合。OR 的工具是線性規劃、模擬、排隊理論、賽局理論和最短路徑演算法。它起源於第二次世界大戰期間，英軍請科學家決定雷達要放在哪裡、船隊該走哪條路線、如何獵殺潛艇；戰後它進入航空、醫院和金融業。其著名成果包括線性規劃的單純形法（丹齊格，1947）與賽局理論（約翰·納許，1994 年諾貝爾獎）。日常例子：GPS 幫你找最短路徑、航空公司排定數千名機組人員與航班、超市決定要開幾條結帳櫃檯。當你面對一個有許多變數的決策、手上有資料、而目標是最優解時，OR 最合適。

Industrial engineering, or IE, asks: this process already exists, so how do we make it work better? It treats a system as a flow: inputs come in, transformations happen, outputs go out. IE observes the real process, measures it, finds the waste, and removes it. Waste means anything that adds cost but no value: waiting, excess motion, overproduction, defects, rework. Its history runs from Frederick Taylor's time-and-motion studies in the early 1900s, through Henry Ford's assembly line, to Lean and just-in-time production at Toyota and Six Sigma at Motorola in the 1980s, which aims for about 3.4 defects per million. Its main tools are time-motion studies, value stream mapping, and ergonomics, designing the workplace to fit the human body. Examples: a factory line, a hospital admission process, an airport security queue. IE fits when the system already exists and the goal is to run it faster, cheaper, and safer.

工業工程（IE）問的是：這個流程已經存在了，要怎麼讓它運作得更好？它把系統當成一股流動：輸入進來、轉換發生、輸出去。IE 觀察真實的流程、量測它、找出浪費、然後移除浪費。浪費指的是任何增加成本卻不增加價值的東西：等待、多餘的動作、過量生產、缺失、重工。它的歷史從 1900 年代初泰勒的時間動作研究，經過福特的裝配線，到豐田的精實與及時生產，以及 1980 年代摩托羅拉的六標準差——目標是每百萬件約 3.4 個缺失。它的主要工具是時間動作研究、價值流圖，以及人因工程——把工作場所設計得符合人體。例子：工廠產線、醫院入院流程、機場安檢隊伍。當系統已經存在、而目標是讓它跑得更快、更便宜、更安全時，IE 最合適。

Systems engineering, or SE, asks: what should we build, and how do we build it right? It treats a system as a purposeful whole that must meet the needs of the people who use it and pay for it. SE works on new, complex systems across their whole lifecycle: eliciting requirements, decomposing the system into parts, defining and controlling the interfaces between parts, integrating, verifying and validating, and managing everything from concept to disposal. In our vocabulary, SE is the discipline that draws the boundary on purpose and controls what crosses it. It matured during the Cold War and Space Race, when projects like Apollo and the early missiles had millions of parts and no single engineer could hold the whole picture. The organizations behind it included Bell Labs, RAND, NASA, and MIT, and INCOSE was founded in 1990 to formalize the field. Its tools include requirements engineering, the V-model from the previous section, the WBS from the next section, and model-based systems engineering, where formal models replace piles of documents. Its famous examples include the Apollo moon landing, the Boeing 787, and the International Space Station, assembled from modules built by 15 countries. SE fits when you are creating something complex from scratch, the parts must work together, and correctness has to be proven.

系統工程（SE）問的是：我們該建造什麼，以及如何把它建對？它把系統當成一個有目的的整體，必須滿足使用者和出資者的需求。SE 在全新而複雜的系統上工作，涵蓋整個生命週期：引出需求、把系統分解成部件、定義並控制部件之間的介面、整合、驗證與確認，並管理從概念到除役的一切。用我們的詞彙來說，SE 就是那門刻意畫出邊界、並控制什麼跨越邊界的學問。它在冷戰與太空競賽期間成熟起來——當時像阿波羅和早期飛彈這樣的專案有數百萬個部件，沒有任何單一工程師能掌握全貌。背後的組織包括貝爾實驗室、蘭德、美國太空總署和麻省理工學院，而 INCOSE 於 1990 年成立，讓這個領域正式化。它的工具包括需求工程、上一節的 V 模型、下一節的 WBS，以及模型化系統工程——用正式模型取代成堆的文件。著名的例子包括阿波羅登月、波音 787，以及由 15 個國家建造的模組組裝而成的國際太空站。當你從零打造一個複雜的東西、部件必須共同運作、而且正確性必須被證明時，SE 最合適。

The three fields read the same system differently:

這三個領域對同一個系統有不同的讀法：

| | OR | IE | SE |
|---|---|---|---|
| Core question | What is the best decision? | How do we make this work better? | What should we build, and how do we build it right? |
| A system is | A mathematical model to optimize | A process: inputs, transformations, outputs | A purposeful whole meeting stakeholder needs |
| The boundary is | The constraints, the set of allowed choices | The start and end of the process flow | A defined boundary with controlled interfaces |
| A good system is | The optimal solution | Smooth flow with minimal waste | Meets requirements, clean interfaces, verifiable |
| Main tools | Linear programming, simulation, queuing theory, game theory | Time-motion studies, value stream mapping, Lean, Six Sigma | Requirements engineering, V-model, WBS, MBSE |
| Use it when | Choosing between many options, with data | The system exists and should run better | Building something new and complex |

| | OR | IE | SE |
|---|---|---|---|
| 核心問題 | 哪個決策最好？ | 怎麼讓它運作得更好？ | 該建造什麼，以及如何建對？ |
| 系統是 | 一個要最佳化的數學模型 | 一個流程：輸入、轉換、輸出 | 一個滿足利害關係人需求的有目的整體 |
| 邊界是 | 約束條件，被允許的選項集合 | 流程的起點與終點 | 一條明確定義、介面受控的邊界 |
| 好的系統是 | 最優解 | 流程順暢、浪費最少 | 符合需求、介面乾淨、可驗證 |
| 主要工具 | 線性規劃、模擬、排隊理論、賽局理論 | 時間動作研究、價值流圖、精實、六標準差 | 需求工程、V 模型、WBS、MBSE |
| 適用時機 | 在許多選項間做選擇，且手上有資料 | 系統已存在，應該運作得更好 | 從零建造新的複雜東西 |

That difference is the richer view: there is no single right way to study a system. The same hospital is a model to optimize for OR (how many beds, how to roster nurses), a process to streamline for IE (how patients move through admission), and a whole to design and verify for SE (building the new hospital). On a real project the three work side by side: SE designs the architecture of the product, IE makes the factory or ward that produces it run smoothly, and OR solves the scheduling and resource puzzles along the way. SE designs the whole, IE improves the process, and OR finds the best choice.

這種差異就是更豐富的視角：研究系統沒有單一正確的方式。同一所醫院，對 OR 是一個要最佳化的模型（要多少病床、怎麼排護士班）、對 IE 是一個要順流化的流程（病人如何通過入院程序）、對 SE 是一個要設計與驗證的整體（興建新的醫院）。在真實專案中，三者並肩工作：SE 設計產品的架構，IE 讓生產它的工廠或病房運作順暢，OR 解決一路上排程與資源的難題。SE 設計整體，IE 改善流程，OR 找出最佳選擇。

One practical question is left: when a field like SE says a big system must be broken into parts, how is that actually done, and in what order?

還剩一個實務問題：當像 SE 這樣的領域說一個大系統必須拆成部件時，實際上該怎麼拆？按什麼順序？

## 7. WBS and Agile: two ways to build a system — WBS 與敏捷：建造系統的兩種方式

To build a big system, you first break it into smaller parts. This is *decomposition*, which is in effect just zooming in, moving down the layers of abstraction. You can break by what the system does (a car needs propulsion, steering, braking, comfort, and safety) or by physical parts (engine, wheels, body, electronics). A good breakdown follows a few rules: the parts do not overlap, together they cover everything, each part has a clear interface with the others, and each part is small enough to estimate, assign, and track, but not so small that you drown in details.

要建造一個大系統，你先把它拆成較小的部分。這就是「分解」，實際上就是放大、沿著抽象層次往下走。你可以按系統做什麼來拆（一輛車需要推進、轉向、煞車、舒適和安全），或按實體部件來拆（引擎、輪子、車身、電子系統）。好的分解遵循幾條規則：部件互不重疊、合起來覆蓋所有東西、每個部件與其他部件有清楚的介面，而且每個部件小到可以估算、分派和追蹤，但又不至於小到讓你淹沒在細節裡。

The usual tool for this is the Work Breakdown Structure, or WBS. It is the classic instrument of big traditional projects, the kind systems engineering handles: aircraft, buildings, defense programs. You start with the whole deliverable at the top and split it into major subsystems, then components, then smaller pieces, level by level, until the leaves are work packages: chunks of work small enough to estimate in hours or days, assign to one owner, put on a schedule, and track. Each work package gets a clear finish line. Because the tree is drawn before any work starts, the whole project can be estimated, scheduled, and budgeted upfront, and later changes go through formal change control, since the boundary was fixed at the start. Decomposition like this creates a hierarchy of nested boundaries, where each part is a system at a lower layer.

常用的工具是工作分解結構（WBS）。它是大型傳統專案的經典工具——就是系統工程處理的那種專案：飛機、建築、國防計畫。你從最上層的完整交付物開始，拆成主要子系統，再拆成組件，再拆成更小的部分，一層一層往下，直到葉節點是工作包：小到可以用小時或天估算、分派給一位負責人、放進時程並追蹤的工作塊。每個工作包都有一條明確的終點線。由於這棵樹在任何工作開始之前就畫好了，整個專案可以事先估算、排程和編列預算，之後的變更要走正式的變更控管，因為邊界在一開始就定死了。這樣的分解創造出一個嵌套邊界的階層，其中每個部件都是較低層次上的一個系統。

Agile comes from software. In 2001, seventeen software practitioners met in Snowbird, Utah, and wrote a short manifesto because projects kept planning everything upfront and then delivering the wrong thing late. The manifesto puts working software, customer collaboration, and responding to change ahead of rigid plans and heavy documentation. In practice, Agile means working in short cycles called sprints, usually one to four weeks long. The team keeps a prioritized list of everything the product might need, called the backlog. At the start of each sprint it pulls the most important items off the top, builds them, and at the end shows a working piece of the product. Users react to what they can actually touch, the team adjusts, and the next sprint begins. The most common Agile framework, Scrum, adds fixed roles such as the product owner and a short daily meeting. Each sprint is a small boundary of its own, and the feedback at the end of every sprint is validation in miniature.

敏捷來自軟體業。2001 年，十七位軟體從業者在猶他州的斯諾伯德聚會，寫下一份短短的宣言，因為專案總是把一切事先規劃好，然後延遲交付錯誤的東西。宣言把可運作的軟體、與客戶協作、回應變化，放在僵硬的計畫和繁重的文件之前。在實務上，敏捷意味著在稱為「衝刺」的短週期中工作，通常一到四週長。團隊維持一份產品可能需要的所有事情的清單，按優先排序，稱為「待辦清單」。每個衝刺開始時，它從最上方拉出最重要的項目、把它們做出來，並在結束時展示一件可運作的產品片段。使用者對他們真正摸得到的東西做出反應，團隊加以調整，然後下一個衝刺開始。最常見的敏捷框架 Scrum 加入了固定的角色（例如產品負責人）和短短的每日站會。每個衝刺本身就是一條小邊界，而每個衝刺結束時的回饋，就是一場縮小版的確認。

The process of building a system is itself a system, and WBS and Agile are two different shapes for it.

建造系統的過程本身就是一個系統，而 WBS 和敏捷是它的兩種不同形狀。

- WBS is upfront and predictive. You decompose the whole system before building anything, fix the boundary early, follow a linear path of design, build, integrate, and test, and check with users at the very end. It is hierarchical in shape and assumes the problem is well defined and the requirements will not change.

  WBS 是事先的、預測式的。你在建造任何東西之前就把整個系統分解好、很早就固定邊界、沿著設計—建造—整合—測試的線性路徑前進，直到最後才和使用者確認。它的形狀是階層式的，假設問題定義良好、需求不會改變。

- Agile is incremental and adaptive. You break off small pieces as you go, build and test each one, show it to users for feedback, and let the overall design emerge over time. It is modular in shape and assumes the problem is uncertain and that learning matters more than predicting.

  敏捷是漸進的、調適式的。你一邊走一邊掰下小塊，逐一建造與測試，拿給使用者換取回饋，讓整體設計隨時間浮現。它的形狀是模組化的，假設問題充滿不確定，而學習比預測更重要。

Both are valid. They differ in when you decompose, fix the boundary, and validate: WBS decomposes first and validates last, while Agile decomposes and validates continuously and lets the boundary evolve. Choose WBS when the problem is well defined and stable, especially for physical or safety-critical systems like buildings, aircraft, or medical devices, where you must prove correctness upfront. Choose Agile when requirements are unclear or likely to change, especially in software, where you learn what users need only by showing them working pieces.

兩者都有效。它們的差別在於何時分解、何時固定邊界、何時確認：WBS 先分解、最後確認；敏捷則持續分解、持續確認，並讓邊界演化。當問題定義良好且穩定時選 WBS，尤其是實體或安全攸關的系統，如建築、飛機、醫療器材——你必須事先證明正確性。當需求不清楚或很可能改變時選敏捷，尤其是在軟體領域——你只有把可運作的片段拿給使用者看，才知道他們需要什麼。

A project is a temporary system: it has parts, connections, a boundary called scope, a goal, a lifecycle, and an outcome no single task produces alone. All of the above, decomposition, boundaries, interfaces, verification, applies to projects too. Systems thinking reaches far beyond machines; it applies to organizations, projects, and everyday decisions.

專案是一個臨時的系統：它有部件、有連結、有一條叫做範圍的邊界、有目標、有生命週期，也有一個任何單一任務都無法獨自產生的成果。以上所說的一切——分解、邊界、介面、驗證——也適用於專案。系統思維遠遠超出機器的範圍；它適用於組織、專案和日常決策。

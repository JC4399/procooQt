# Procoo, Level 1 — 初級指南

A first-time introduction to Procoo: what you see, what a skill is, how to start building your own, and where the other parts fit in. No technical background is needed.

本文是 Procoo 的入門指南，從開啟應用程式後看到的畫面講起，說明什麼是技能、如何開始建立自己的技能，最後簡介 Procoo 的其他功能。不需要技術背景。

---

## 1. Your first chat — 你的第一次對話

### 1.1 What you see — 你看到的

When the app opens you land in the `Default` session, on the Chat page, with one panel in front of you. Inside the panel: a tab bar across the top, a transcript area in the middle, a token bar below it, and an input row at the bottom. A narrow rail sits on the right edge of the panel — that is the skill dock, which you will meet in section 2.

開啟 Procoo 後，畫面會停留在預設工作階段的對話頁，前方只有一個面板。面板由上而下分為四部分：頂端是分頁列，中央是對話記錄區，其下是 token 數列，底部是輸入列。面板右側有一條窄軌，那是技能側欄，將在第 2 節詳述。

The title bar across the top of the window holds the session name and the page tabs: Chat, Editor, Automation, Notification. The app opens on Chat.

視窗頂端是一條標題列，顯示工作階段名稱與四個頁面標籤：對話、編輯器、自動化、通知。應用程式啟動時預設顯示對話頁。

### 1.2 Start a chat — 開始一場對話

If the panel has no tabs yet, click `+` in the tab bar to create one. Then type in the input row and press Enter, or click the Send button.

如果面板中還沒有分頁，點選分頁列上的「+」建立一個。接著在輸入列輸入文字，按 Enter 或點選送出即可開始。

The model starts working. Cards appear in the transcript area as the turn progresses: the model thinks, it may call a tool, it reads the result, and it writes its answer. The turn runs until the model judges the task done.

模型隨即開始運作。隨著回合推進，對話記錄區會逐張產出卡片：模型先進行推理，可能呼叫一個工具，讀取結果，最終給出答案。整個回合持續運行，直到模型認為任務完成為止。

### 1.3 Chat cards — 對話卡片

Each piece of a turn becomes a card in the transcript, in the order it happened. The card type tells you which part of the work it holds.

每一輪的每個步驟都會變成對話記錄中的一張卡片，按發生的順序排列。卡片的類型標示了它所記錄的工作環節。

| Card | What it holds |
|---|---|
| User | your message, verbatim |
| Waiting | a headerless scanner, shown while a turn runs but has produced nothing yet |
| Thinking | the model's reasoning, streamed as plain text |
| Response | the answer, rendered as Markdown while it streams, including tables, links and maths |
| Tool call | the tool name, its permission mode, and the arguments as YAML |
| Tool result | the tool's output, with the tool name in the subtitle; failures look the same, as text |
| Context banner | what the chat was given, neutral at the start and orange for an update after you changed skills |

| 卡片 | 內容 |
|---|---|
| 使用者 | 你的訊息，原文呈現 |
| 等待中 | 回合已啟動但尚未產出任何內容時顯示的空白卡片 |
| 思考 | 模型的推理過程，以純文字逐字呈現 |
| 回應 | 最終答案，以 Markdown 格式邊生成邊渲染，可包含表格、連結與數學公式 |
| 工具呼叫 | 工具名稱、權限模式與以 YAML 格式呈現的參數 |
| 工具結果 | 工具的輸出內容，工具名稱顯示於副標題；失敗與成功的呈現方式相同，均為文字 |
| 上下文橫幅 | 對話被賦予的內容；初始為中性色，修改技能後更新為橘色 |

Every card header shows an icon, a title, the token count for that card, and a collapse arrow. While a turn is running, only the last twelve cards are built expanded; anything older sits as a header until you click it.

每張卡片的標題列顯示圖示、標題、該卡片的 token 數量以及摺疊箭頭。回合運行期間，僅最近十二張卡片保持展開狀態，更早的卡片收為標題，需點擊後才會展開。

Hovering over a card header reveals two actions, both disabled while a generation is running: the trash icon deletes the turn that card belongs to; the reload icon on a user card regenerates from that message and discards everything after it.

將游標懸停在卡片標題上會出現兩個按鈕，生成期間兩者皆無法使用。垃圾桶圖示會刪除該卡片所屬的整個回合；使用者卡片上的重載圖示則會從該則訊息重新生成，並捨棄其後的所有內容。

### 1.4 Tab status and the input row — 分頁狀態與輸入列

The dot on each tab tells you what the chat is doing without opening it:

每個分頁上的圓點標示該對話的當前狀態，無需打開即可查看：

| Dot | Status | Meaning |
|---|---|---|
| grey | `EMPTY` | created, no messages yet |
| blue, blinking | `RUNNING` | generating |
| amber, blinking | `WAITING` | generating, paused for a tool approval |
| green | `FINISHED` | has messages, idle |
| red | `ERROR` | last turn failed or you stopped it |

| 圓點 | 狀態 | 含義 |
|---|---|---|
| 灰色 | 空 | 已建立，尚無訊息 |
| 藍色（閃爍） | 運行中 | 正在生成內容 |
| 琥珀色（閃爍） | 等待核准 | 生成中，暫停等待工具核准 |
| 綠色 | 已完成 | 有內容，目前閒置 |
| 紅色 | 出錯 | 上一回合失敗或被手動停止 |

`+` in the tab bar opens a new chat in the same panel and copies the skills, tool modes, and model of the chat you are on. `×` deletes the chat; the file does not come back.

分頁列上的「+」會在同一面板內開啟新對話，並沿用當前對話的技能、工具模式與模型設定。「×」則刪除該對話，對應檔案無法復原。

The input row is at the bottom of the panel. Type in the box and press Enter, or click Send. While a chat is generating, the Send button becomes Stop.

輸入列位於面板底部。在輸入框中輸入文字後，按 Enter 或點選送出即可發送。對話正在生成時，送出按鈕會變為停止。

Two controls appear when the pointer enters the row: a checkbox that locks Enter, for writing a multi-line message without sending it early, and the auto-scroll toggle, on by default and faded out whenever it is paused.

游標進入輸入列時，會顯示兩個控制項：一個勾選框用於鎖定 Enter 鍵，以便輸入多行文字而不誤觸發送；另一個是自動捲動開關，預設開啟，暫停時會自動淡出。

Stopping a turn keeps the partial transcript and marks the chat as stopped — the tab shows a red dot.

停止一個回合後，已產出的內容會被保留，對話標記為已停止狀態，對應分頁上會顯示紅色圓點。

### 1.5 Stopping, redoing, and the approval bar — 停止、重做與核准列

Stop cancels the current turn and keeps whatever it had produced so far.

停止操作會取消當前回合，但已產出的內容會保留。

The reload icon on a user card regenerates from that message and discards everything after it. The trash icon deletes the turn its card belongs to. Both are ways to redo a step without starting a new chat.

使用者卡片上的重載圖示會從該則訊息重新生成，並捨棄其後的內容；垃圾桶圖示則刪除該卡片所屬的整個回合。兩者都是不開啟新對話即可重做某一步驟的方式。

The approval bar appears above the input row. When a tool set to Ask is called by the model, generation pauses and a bar appears naming the tool and the arguments it wants to pass.

核准列顯示在輸入列上方。當模型呼叫一個設為「詢問」模式的工具時，生成會暫停，同時出現一條橫幅，列明工具名稱與它想傳入的參數。

Approve runs the call and the turn continues. Deny skips it and tells the model that execution was denied — usually you get an answer built from what the model already had, or a second attempt by another route. Stop cancels the whole turn rather than deciding on that one call.

核准後該次呼叫會執行，回合繼續進行。拒絕則跳過該次呼叫，並告知模型執行已被拒絕——通常模型會基於已有資訊組織答案，或換另一條路徑重試。停止則是取消整個回合，而非僅對該次呼叫做決定。

Only Ask raises the bar. Allow runs straight through, and Block refuses before the model sees anything.

只有「詢問」模式會觸發核准列。「允許」模式直接執行，「封鎖」模式則在模型尚未看到該工具時就直接拒絕。

Approvals belong to a single chat. A panel waiting on one blinks amber, so you can find it again after switching tabs.

核准綁定在單一對話上。正在等待核准的面板會以琥珀色閃爍，方便切換分頁後重新找到它。

### 1.6 What the numbers at the bottom mean — 底部數字的意思

Five values sit above the input row and describe the active chat:

輸入列上方的五個數值描述當前對話的狀態：

| Item | Meaning |
|---|---|
| Input tokens | the size of what the next turn will send: system prompt, loaded skills, and the whole conversation |
| Output tokens | what the chat has produced over all its turns |
| Activated | number of loaded skills |
| Allow / Ask / Block | tool counts in each permission mode |
| Model | the model name this chat uses |

| 項目 | 含義 |
|---|---|
| 輸入 token | 下一回合將送出的總量：系統提示詞、已載入技能與整段對話 |
| 輸出 token | 該對話迄今累計產出的 token 數 |
| 已啟動 | 已載入的技能數量 |
| 允許／詢問／封鎖 | 各權限模式下的工具數量 |
| 模型 | 該對話所使用的模型名稱 |

The input token count climbs as the conversation grows, approaching the model's context window limit. Once the configured limit is crossed, Procoo asks the model to summarise the conversation and starts a new chat from that summary, condensing the work so far into its opening context.

輸入 token 數會隨對話增長而持續上升，逐漸逼近模型的上下文視窗上限。一旦超過設定的閾值，Procoo 會要求模型對對話進行摘要，並從該摘要開啟新對話，把之前的工作概括成新對話的開頭。

The tool counts tell you what a turn will run into. Anything in Block is refused without asking, and anything in Ask stops the turn at the approval bar.

工具數量告訴你這輪會碰到什麼：設為「封鎖」的工具會直接被擋下；設為「詢問」的工具則會讓回合在核准列停下。

---

## 2. Skills — 技能

### 2.1 What a skill is and how it works — 技能是什麼、如何運作

A skill is a folder on disk under `capabilities/skills/`, with a `SKILL.md` at its entry and optionally a `scripts/` folder next to it.

技能是 `capabilities/skills/` 目錄下的一個資料夾，以 `SKILL.md` 為入口，旁邊可選一個 `scripts/` 子目錄。

The `SKILL.md` has two parts. At the top, a short metadata block names the skill and describes what it does and when to use it. Below that, the body holds the instructions: the steps of the job, the conventions to follow, and pointers to any reference files.

`SKILL.md` 分為兩部分。頂端是一小段中繼資料，為技能命名並說明它做什麼、什麼時候用。下方的主體則包含具體指令：工作步驟、須遵循的規範，以及指向參考檔案的指引。

When you tick a skill in the dock, two things happen on every turn from that point on:

在側欄中勾選一個技能後，自該時刻起，每個回合都會發生以下兩件事：

1. The full instructions of the skill are added to the system prompt that the model reads.
2. Each script in the skill's `scripts/` folder is registered as a tool the model may call. The model reads the script's docstring to learn what the tool does, what arguments it takes, and when to call it.

1. 技能的完整指令會加入系統提示詞，模型每個回合都能讀取。
2. 技能 `scripts/` 目錄中的每個腳本都會被註冊為模型可呼叫的工具。模型通過 docstring 了解工具的功能、參數與適用時機。

The description in the docstring is the part that decides whether the tool gets used, used correctly, or not used at all. The model has no way to infer what an argument means unless the description says so. That is why a thin description fails while the code behind it is fine.

docstring 中的描述決定了工具是否會被使用、是否被正確使用。模型無法自行推斷參數的含義——若描述未加說明，模型便無從得知。這正是描述過簡會導致工具失靈、而程式碼本身卻沒有問題的原因。

### 2.2 Navigating the skill panel — 操作技能側欄

Each panel has a narrow rail on its right edge. Clicking it expands the skill dock over the transcript. While the dock is open, drag its left edge to resize it, or click anywhere outside to close it.

每個面板右側有一條窄軌，點擊後會展開技能側欄，覆蓋在對話記錄上方。側欄展開時，可拖曳其左邊緣調整寬度，或點擊側欄外任意位置將其關閉。

**Searching.** The search field at the top of the dock filters the skill tree by name. Folders that match are opened; folders that lead nowhere are hidden. Click `×` to clear the search and restore the collapse state you had.

**搜尋。** 側欄頂端的搜尋欄可透過名稱過濾技能樹。匹配的資料夾會展開，無匹配項的資料夾則隱藏。點擊「×」可清除搜尋，恢復原有的摺疊狀態。

**Ticking a skill.** Ticking a skill sends its instructions into the system prompt and registers its tools. Unticking removes the registration for the next turn. Instructions already in the conversation cannot be pulled out — the agent keeps the old text in its history — so Procoo warns you when you untick a skill that has already run.

**勾選技能。** 勾選一個技能後，其指令會進入系統提示詞，其工具也會被註冊。取消勾選則自下一回合起停止註冊。已進入對話的指令無法移除——代理人會將舊文字保留在歷史中——因此取消一個已執行過的技能時，Procoo 會發出警告。

**Setting tool modes.** Tools sit under the skill that owns them. Each tool has a mode: Allow runs the call without asking, Ask raises the approval bar before it runs, and Block refuses it before the model sees anything. Set each tool to the mode that fits how much you trust it.

**設定工具模式。** 工具列於其所屬技能下方，每個工具有三種模式：允許（直接執行）、詢問（執行前於核准列暫停）、封鎖（在模型看到前即拒絕）。根據對工具的信任程度設定對應模式。

**Choosing the model.** The model dropdown in the dock lists every model in the config and marks the one this chat uses. Picking another changes the chat from its next turn without reloading anything or losing the transcript.

**選擇模型。** 側欄中的模型下拉選單列出設定中的所有模型，並標記當前對話所使用的模型。切換模型自下一回合生效，不會重新載入或丟失對話記錄。

**Presets.** The preset field saves your current skill and tool selection under a name. Picking a saved preset later applies the whole selection at once.

**預設檔。** 預設檔欄位可將目前的技能與工具選擇儲存為一個名稱，之後從下拉選單中選取即可一次性套用整套設定。

All changes apply to the active chat immediately and are written into that chat's record.

所有變更會立即套用到當前對話，並寫入該對話的記錄中。

### 2.3 Two built-in skills — 兩個內建技能

Every Procoo chat comes with two skills loaded by default: `basic-ops` and `agent-principle`. They are what turn a raw language model into an agent that can actually work for you.

每個 Procoo 對話預設載入兩個技能：`basic-ops` 與 `agent-principle`。正是這兩個技能將原始語言模型轉變為真正能夠執行工作的代理人。

**basic-ops: the hands**

**basic-ops：執行能力**

`basic-ops` gives the agent the tools to act on your machine. It registers a set of file tools: reading files and documents, creating and editing files, searching directories, running code or shell commands, and managing a records database.

`basic-ops` 給代理人操作檔案的能力。它註冊了一組檔案工具：讀取檔案與文件、建立與編輯檔案、搜尋目錄、執行程式碼或 shell 指令，以及管理記錄資料庫。

Each tool has a clear job. `read_file` reads text files, PDFs, and images. `edit_file` creates, edits, or deletes a file. `search_dir` finds files by name pattern and by content. `execute_script` runs Python code or a shell command. `init_db` and `access_db` manage a records database.

每個工具各司其職：`read_file` 讀取文字檔案、PDF 與圖片；`edit_file` 建立、編輯或刪除檔案；`search_dir` 依路徑模式與內容搜尋檔案；`execute_script` 執行 Python 程式碼或 shell 指令；`init_db` 與 `access_db` 管理記錄資料庫。

The skill also carries a tool selection policy: use the dedicated file tool for the job, not a shell command. Reading a file is `read_file`, not `cat`. Editing is `edit_file`, not `sed`. This rule exists because the dedicated tools are safer, return structured results, and avoid shell injection risks.

該技能同時包含一條工具選擇準則：有專用工具時應使用專用工具，而非以 shell 指令替代。讀取檔案使用 `read_file` 而非 `cat`，編輯檔案使用 `edit_file` 而非 `sed`。原因是專用工具更安全，能回傳結構化結果，並避免 shell 注入風險。

Without `basic-ops`, the model can talk all day but cannot touch anything on disk. It is a chatbot. With it, the agent can read your code, edit your files, search your project, run your tests, and store records. That is the difference between a conversation and a worker.

沒有 `basic-ops`，模型只能進行對話，無法觸及磁碟上的任何內容——它還只是一個聊天機器人。有了它，代理人便能讀取程式碼、編輯檔案、搜尋專案、執行測試並儲存記錄。這便是對話與執行之間的本質差異。

**agent-principle: the method**

**agent-principle：工作方法**

`agent-principle` gives the agent a method for approaching work. It describes four phases:

`agent-principle` 給代理人一套做事的方法，涵蓋四個階段：

| Phase | What it does |
|---|---|
| Align | Before the first step: read the skill and references, confirm the goal, deliverable, checking items, and assumptions. Wait for the user's go-ahead. |
| Proceed | Work to completion on the agreed method. Ask when something is ambiguous; decide when the material settles the question; record the decision. Keep momentum. |
| Check | Verify the work against the checking items agreed in Align. If it falls short, go back to Proceed. |
| Close and learn | Report the outcome and any deviations. Ask what missed the mark. Extract lessons from user corrections and write them into the skill or references after confirmation. |

| 階段 | 內容 |
|---|---|
| 對齊 | 動工前：閱讀技能說明與參考資料，確認目標、產出形式、檢查項目與假設。待使用者確認後再開始執行。 |
| 推進 | 依照約定方法執行至完成。遇有歧義時提問，材料足以判斷時做出決定並記錄，保持推進節奏。 |
| 檢查 | 以對齊階段約定的檢查項目驗證成果，未達標則回到推進階段繼續。 |
| 收束與學習 | 報告成果與偏離之處，詢問哪些方面未達標。從使用者回饋中提煉教訓，經確認後寫入技能或參考資料。 |

The skill also sets the judgment rules: ask when the purpose is ambiguous and a wrong guess is expensive; decide when the material settles the question; move on when options are equally valid and the choice is reversible. And it sets the honesty standard: report where the work departed from the agreed method, state every assumption, and say early when something is wrong.

該技能同時確立了判斷準則：目的模糊且誤判代價高時應提問；材料足以判斷時應做出決定並記錄；選項一樣好且可以反悔時應繼續推進。它也確立了誠實標準：偏離約定方法時須報告，所有假設須明確陳述，出現問題時須及早說明。

Without `agent-principle`, the model just starts doing whatever comes to mind and reports success regardless. With it, the model pauses to confirm intent, picks a method, executes with discipline, verifies its work, and reports honestly.

沒有 `agent-principle`，模型會隨興而行，無論結果如何皆回報已完成。有了它，模型會先確認意圖、選擇方法、有紀律地執行、驗證成果，並如實報告。

**Together: hands + method = an agent**

**執行能力＋工作方法＝代理人**

`basic-ops` is the capability layer: what the agent can do. `agent-principle` is the method layer: how the agent should approach work. The language model alone is a stateless text function: you ask, it answers, nothing persists. Give it the tools and the method, and it becomes an agent: something you hand a task to once, and it runs step after step on its own.

`basic-ops` 定義代理人能執行什麼，`agent-principle` 定義代理人應如何工作。語言模型本身是無狀態的文字函數——問則答，不問則無，不留任何痕跡。賦予它執行工具與工作方法，它才能成為代理人：交出一項任務，它便能逐步自行推進。

### 2.4 Three things you can put in a skill — 技能可以放的三種東西

A skill is useful because it turns something you would otherwise retype into every conversation into something the model reads once and applies every time. The three things a skill can hold are:

技能的价值在於：將原本每次對話都需重新輸入的內容，轉化為模型只需讀取一次便可在每次適用時套用的常駐知識。技能裡可以放的內容有三類：

| Type | What it is | Shape |
|---|---|---|
| Procedure | steps for doing a task | "When the user asks to X: step 1, step 2, step 3" |
| Information | context the model does not have | "Our deploy pipeline works like this: ..." |
| Script | a program the model runs | SKILL.md says "call `collect.py` when the user asks for data"; `collect.py` does the actual work |

| 類型 | 說明 | 形式 |
|---|---|---|
| 程序 | 執行某項任務的步驟 | 「當使用者要求 X 時：步驟一、步驟二、步驟三」 |
| 資訊 | 模型不具備但應知的背景知識 | 「我們的部署管線運作方式如下：……」 |
| 腳本 | 供模型執行的程式 | SKILL.md 中寫明「使用者要求資料時呼叫 `collect.py`」，由 `collect.py` 執行實際工作 |

A procedure is the steps you want the model to follow. Information is the background knowledge you feed the model: your naming conventions, your database schema, your company policy. A script is a program you write for the model to run; SKILL.md just says when to call it and with what arguments, while the code does the actual work.

程序是你希望模型依循的步驟。資訊是你提供給模型的背景知識：命名規範、資料庫結構、公司政策。腳本是你撰寫好供模型執行的程式；SKILL.md 只負責說明呼叫時機與參數，實際工作由程式碼完成。

The point of all three: a skill moves knowledge out of your keyboard and into the files on disk, where the model reads it and applies it without you retyping it.

三者的共同點：技能把知識從你的鍵盤搬到磁碟檔案裡，使模型讀取後即可套用，無需你再次輸入。

### 2.5 Why skills make the agent better over time — 技能為什麼讓代理人越來越強

"Learning" with skills does not mean retraining the model. The weights do not change. When we say the agent learned from a skill, we mean a durable change was made to the skill files on disk, so the next similar task goes better.

在技能的語境中，「學習」並非重新訓練模型，權重並未改變。當我們說代理人從技能中有所學習時，指的是磁碟上的技能檔案被真正改掉了，使得下次類似任務能執行得更順暢。

Improving a skill happens through three edit operations: **append** adds new content (a step that came up, an edge case, a worked example); **refine** rewrites existing content (fix a wrong step, sharpen a description); **remove** deletes what is obsolete or harmful (dead scripts, outdated steps). A skill that only grows becomes bloated and contradictory, so all three operations are needed.

改進技能依賴三種編輯操作：**新增**（補入新出現的步驟、邊界案例或值得保留的範例）、**修正**（改寫錯誤步驟或把描述寫清楚）、**移除**（刪除過時或有害的內容）。只增不刪會使技能臃腫且自相矛盾，因此三種操作缺一不可。

The loop around those edits: act (run the task using the skill), observe (did it succeed, where did it stumble), diagnose (missing knowledge means append, wrong knowledge means refine, stale knowledge means remove), apply (make the edit), verify (re-run the task to confirm the change helps and does not break anything else).

圍繞這些編輯的迴圈如下：執行（以技能運行任務）→ 觀察（是否成功，何處受阻）→ 診斷（知識不足則新增，知識有誤則修正，知識過時則移除）→ 套用（進行編輯）→ 驗證（重新執行任務，確認修改有效且未破壞其他功能）。

Over time, a maintained skill set compounds: each task is slightly easier than the last, the skills sharpen, and the agent gets better without the weights changing. An unmaintained skill set drifts: skills rot, records go stale, the agent confidently repeats outdated behavior, and trust erodes. Memory decays unless it is maintained.

長遠來看，經過維護的技能集會產生複利效應：每項任務都比前一次略為輕鬆，技能日益精確，代理人持續進步，而模型權重紋絲未動。反之，缺乏維護的技能集會漸趨漂移：技能失靈、記錄過時、代理人自信地重複過時行為，信任逐漸磨損。記憶若不維護，便會衰退。

---

## 3. Building your skill set — the mindset — 建立技能集的心法

### 3.1 Why and when to build a skill — 為什麼、何時建技能

The signal is simple: you find yourself pasting the same instructions or context into every conversation. The moment that happens, the right question to ask is: is this something the model needs every time, or just this once?

什麼時候該建技能？訊號其實很直觀：你發現自己每次對話都在貼上相同的指令或背景知識。一旦這個情況發生，就該問自己：這些內容是模型每次都需要，還是僅此次需要？

If the answer is every time, it belongs in a skill. If it is just this once, a plain instruction in the chat is enough.

若答案是「每次都需要」，它就應該被納入技能，成為模型可以反覆讀取的常駐知識；若僅是「此次需要」，在對話中直接說明即可，無須動用技能。

The purpose of a skill is to move knowledge out of your keyboard and into the files on disk, where the model reads it and applies it on every relevant turn without you retyping it.

技能的本質，就在於把知識從你的鍵盤搬到磁碟檔案裡，使模型在每個相關回合都能讀取並套用，而無需你重複輸入。

### 3.2 Direct processors — 直接處理器

A direct processor is a skill whose job is to produce an action or a reading: it does something, or it observes something and reports back.

直接處理器的職責很明確：產出一個行動，或一次觀察。換句話說，它要麼執行某項操作，要麼觀測某項狀態並回報結果。

A script that formats a file. A script that queries a database and returns a summary. A procedure for cleaning a dataset. The boundary is clean: clear input, one job, clear output. You can test it in isolation without thinking about the rest of your skill set.

格式化檔案的腳本、查詢資料庫並回傳摘要的腳本、清理資料集的步驟，都是直接處理器的典型範例。它們的共同特徵是邊界清晰：輸入明確、職責單一、輸出明確，因此可以獨立測試，無需考慮技能集中的其他部分。

This is the obvious kind, and it is the first thing most people write. You notice a task you do repeatedly, you write the steps or the script, and you have a direct processor.

這也是最直覺的類型，通常是多數人撰寫的第一個技能。當你注意到一項反覆進行的工作，只需寫下步驟或腳本，一個直接處理器便已成形。

### 3.3 Indirect processors — 間接處理器

An indirect processor is a skill whose job is to make other skills work better. It does not produce an action by itself. It holds the context, conventions, templates, and reference data that direct skills need to do their job correctly.

間接處理器的職責與直接處理器截然不同：它本身不產出行動，而是讓其他技能運作得更好。它存的是直接處理器正確執行工作所需的背景知識、規範、模板與參考資料——本身不做事，但讓做事的技能不會偏離軌道。

The signal that you need one: two direct skills are reaching for the same piece of context. Instead of copying that context into both, pull it out into a shared indirect skill. Now both direct skills point to it, and when the context changes you change it in one place.

什麼時候需要它？訊號很明確：當兩個直接處理器開始爭用同一塊背景知識時。與其將該背景複製到兩者之中，不如將它抽離出來，建立一個共用的間接技能。兩個直接處理器都指向它，日後背景更動時只需修改一處，而非兩處。

Indirect skills are the infrastructure of your skill set. They are the conventions, the schemas, the style guides, and the reference documents that keep your direct skills from drifting apart.

從整體來看，間接技能構成技能集的底層基礎設施。規範、資料結構、風格指南與參考文件——正是這些不直接做事的內容，使各直接處理器不至各行其是、互相偏離。

### 3.4 When skills grow — 技能長大時

As your skill set grows, two things happen: skills start overlapping, and skills start drifting.

技能集隨著使用而擴大，兩種現象便幾乎必然隨之而來：技能之間開始重疊，以及個別技能開始漂移。

**Splitting.** When a skill does two different jobs — it collects data and also formats it, for instance — it is two skills wearing a trench coat. The signal is that you find yourself writing "this part is for X and this part is for Y." That is your boundary drawn in the wrong place. Split the skill: one direct processor for data collection, one for formatting, and if both need the same context, a shared indirect skill for it.

**拆分。** 當一個技能同時承擔兩項不同工作——例如既收集資料又格式化資料——它實質上是兩個技能共用了同一個外殼。訊號是你開始寫「這部分是給 X，那部分是給 Y」，這表示邊界劃設不當，應予拆分：一個直接處理器負責收集，一個負責格式化；若兩者需要相同的背景知識，再抽離一個共用的間接技能。

**Drift.** A skill that has not been maintained starts to contradict itself: a step that is no longer true, a description that no longer matches what the skill does, a script that has been replaced but not removed. This is the decay mode. The three maintenance operations from section 2.5 — append, refine, remove — are how you fight it.

**漂移。** 長期未維護的技能會逐漸自相矛盾：某一步驟已不再成立，某個描述已與實際行為不符，某個腳本已被替代但未移除。這是技能衰敗的典型模式。第 2.5 節所述的三種維護操作——新增、修正、移除——正是對付漂移的手段。

**The coupling test.** The question that tells you whether your boundaries are in the right place: can you change the inside of skill A without touching skill B? If not, the two are coupled where they should not be. The fix is usually to find the shared piece and pull it into an indirect skill.

**耦合測試。** 判斷邊界是否劃設得當，標準很簡單：修改技能 A 的內部時，能否不觸及技能 B？若不能，則兩者在不該耦合的地方產生了耦合。解法通常是找到那個共享片段，將其抽離至間接技能中。

The principle that ties it together: the job of skill design is to keep each skill's boundary clean, so that the system of skills stays simple and maintainable as it grows.

貫穿以上各項原則的核心只有一句話：技能設計的關鍵是維持每個技能的邊界清晰。只要邊界清晰，整個技能系統在持續成長中就能保持簡潔與可維護性。

---

## 4. The rest of Procoo — Procoo 的其他部分

### 4.1 Sessions — 工作階段

A session is a named group of chats, each with its own panel layout. Sessions live in the title bar: clicking the session name opens the session list, where you can switch, create with `+`, or delete.

工作階段是一組命名的對話，各自保有獨立的面板布局。所有工作階段的管理入口都在標題列：點擊工作階段名稱即可開啟清單，從中進行切換、以「+」建立新工作階段，或刪除既有工作階段。

Deleting a session deletes its chats with it. `+ Win` creates a session and opens it in a window of its own.

需要注意的是，刪除工作階段會同時刪除其下的所有對話，無法復原。「+ Win」則建立一個新工作階段並在獨立視窗中開啟，適合需要同時處理不同脈絡的情況。

Use sessions to separate your work contexts: one for coding, one for writing, one for research. Each keeps its own skills, tools, and panel arrangement.

實務上，工作階段最直接的用途是區隔不同的工作脈絡：一個用於寫程式、一個用於寫作、一個用於研究。每個工作階段各自保有獨立的技能、工具與面板配置，互不干擾。

### 4.2 Multi-window — 多視窗

`+ Win` in the session list creates a second window running a different session, with its own panels, tabs, and docks. Both windows read the same session list, so a session created in one appears in the other without a refresh.

清單中的「+ Win」會開啟第二個視窗，運行另一個工作階段，該視窗擁有自己的面板、分頁與側欄。兩個視窗共享同一份工作階段清單，因此任一視窗建立的工作階段會立即顯示在另一視窗中，無需重新整理。

Use it to run two sessions side by side: one doing the work, the other planning or monitoring.

最常見的用法是並行運行兩個工作階段：一個負責執行具體工作，另一個負責規劃或監控進度。

### 4.3 Editor — 編輯器

The editor is a separate window with a file tree and a code pane. It opens from three places: Open Editor in the skill dock, Debug on an error notification, and Edit on an automation card. The last two also load the file they refer to.

編輯器是一個獨立視窗，包含檔案樹與程式碼面板。開啟途徑有三：技能側欄中的「開啟編輯器」、錯誤通知上的「除錯」，以及自動化卡片上的「編輯」。後兩者會同時打開它們指向的檔案，方便直接查看或修改。

Files open read-only. Click Edit to unlock the buffer, make your changes, then Save to write them to disk or Cancel to discard them.

檔案預設為唯讀。點選「編輯」可解鎖緩衝區，修改完成後按「儲存」寫入磁碟，或按「取消」捨棄變更。

### 4.4 Automation — 自動化

An automation is a script that runs on a cron schedule or when an HTTP event arrives. It lives under `capabilities/automations/` as a directory with an `AUTOMATION.py` file.

自動化是一個依排程（cron）或 HTTP 事件觸發而運作的腳本，存放於 `capabilities/automations/` 目錄下，以一個包含 `AUTOMATION.py` 的資料夾為單位。

The Automation page lists every automation Procoo finds, one card each. A card shows the name, description, activation type, schedule or event, and the result of the last run. The toggle enables or disables it. Run now starts it immediately — the result arrives as a notification. Edit opens its `AUTOMATION.py` in the editor.

自動化頁面列出 Procoo 偵測到的所有自動化項目，各以一張卡片呈現。每張卡片顯示名稱、描述、觸發類型、排程或事件，以及最近一次執行的結果。卡片上的開關用於啟用或停用；「立即執行」會馬上觸發該自動化，結果以通知形式呈現；「編輯」則在編輯器中開啟其 `AUTOMATION.py` 以供修改。

Notifications appear on the Notification tab with three badges: grey for logs, amber for info, red for errors. An error card offers a Debug button that opens the failing automation in the editor.

通知顯示於通知頁籤，附有三個徽章：灰色代表日誌、琥珀色代表資訊、紅色代表錯誤。錯誤卡片提供「除錯」按鈕，可將失敗的自動化開啟於編輯器中，方便檢視日誌與程式碼的對應關係。

### 4.5 Obsidian plugin — Obsidian 外掛

A local control server on port 12841 lets Obsidian open Procoo sessions. A marked span in a note stores a session ID; the context menu can open that session or start one from the selected text.

本機控制伺服器（端口 12841）讓 Obsidian 得以開啟 Procoo 工作階段。筆記中標記的文字片段會儲存一個工作階段 ID，透過右鍵選單可以開啟該工作階段，或從選取的文字建立新工作階段。

Use it to link your notes to your agent work: write a note, mark the relevant span, and open the session that has been working on it.

這個功能讓筆記與代理人的工作得以串接：撰寫一篇筆記、標記相關片段、然後開啟一直在處理該內容的工作階段，即可在筆記與對話之間自由切換。

---

## 5. The config file — 設定檔

All settings live in `config/config.yaml` (copy the committed template `config/config_template.yaml` to get started; the real file is gitignored).

所有設定集中在 `config/config.yaml`（複製版本庫中的範本 `config/config_template.yaml` 即可開始使用；實際檔案已列入 `.gitignore`）。

| Section | What it sets |
|---|---|
| `llm` | model entries for the dropdown; one has `default: true` |
| `paths` | where skills, automations, and chat data live |
| `limits` | byte / token ceiling that triggers auto-summarisation |
| `agent` | base system prompt + summary prompt |
| `server` / `control_server` / `subagent` | local HTTP server ports and API keys |
| `basic_ops` | service URLs called by `read_file` and `access_db` (OCR, semantic search) |

| 區段 | 用途 |
|---|---|
| `llm` | 下拉選單中的模型清單；其中一個設為 `default: true` |
| `paths` | 技能、自動化與對話資料的存放路徑 |
| `limits` | 觸發自動摘要的位元組／token 上限 |
| `agent` | 基礎系統提示詞與摘要提示詞 |
| `server` / `control_server` / `subagent` | 本機 HTTP 伺服器端口與 API 金鑰 |
| `basic_ops` | `read_file` 與 `access_db` 所呼叫的外部服務網址（文字辨識、語意檢索） |

# Procoo, Level 1 — 初級指南

A first-time introduction to Procoo. It covers what you see when you open the app, what a skill is, how to start building your own skills, and where the other parts of the app fit in. No technical background is needed.

本文是 Procoo 的入門指南。內容從開啟應用程式後看到的畫面談起，說明什麼是技能、如何開始建立自己的技能，最後介紹 Procoo 的其他功能。閱讀本文不需要技術背景。

---

## 1. Your first chat — 你的第一次對話

### 1.1 What you see — 你看到的

When the app opens, you land in the `Default` session on the Chat page, with one panel in front of you. The panel has four parts, top to bottom: a tab bar across the top, a transcript area in the middle, a token bar below it, and an input row at the bottom. A narrow rail runs along the right edge of the panel. That rail is the skill dock, which you will meet in section 2.

開啟 Procoo 後，畫面停在名為 `Default` 的預設工作階段，位於 Chat 頁，眼前只有一個面板。面板自上而下分為四部分：頂端為分頁列，中央為對話記錄區，其下為 token 統計列，底部為輸入列。面板右緣有一條窄軌，即技能側欄，詳見第 2 節。

The title bar across the top of the window shows the session name and four tabs: Chat, Editor, Automation, and Notification. The app opens on Chat.

視窗頂端為標題列，顯示工作階段名稱與四個分頁：Chat、Editor、Automation、Notification。應用程式啟動時預設顯示 Chat 分頁。

### 1.2 Start a chat — 開始一場對話

If the panel has no tabs yet, click `+` in the tab bar to create one. Type your message in the input row, then press Enter or click Send.

若面板尚未建立分頁，點選分頁列上的「+」新增一個。接著在輸入列輸入文字，按 Enter 或點選 Send，即可開始對話。

The model starts working. As the turn progresses, cards appear in the transcript area: the model thinks, may call a tool, reads the result, and writes its answer. The turn runs until the model decides the task is done.

模型隨即開始運作。隨著回合推進，對話記錄區會陸續出現卡片：模型先進行推理，可能呼叫工具，讀取結果，最後給出答案。整個回合持續執行，直到模型判定任務完成為止。

### 1.3 Chat cards — 對話卡片

Each part of a turn becomes a card in the transcript, in the order it happened. The card type tells you which part of the work it holds.

每一回合的每個環節，都會在對話記錄中形成一張卡片，並依發生的順序排列。卡片類型標示該卡所記錄的工作環節。

| Card | What it holds |
|---|---|
| User | your message, verbatim |
| Waiting | a headerless scanner, shown while a turn runs but has produced nothing yet |
| Thinking | the model's reasoning, streamed as plain text |
| Response | the answer, rendered as Markdown while it streams, including tables, links, and math |
| Tool call | the tool name, its permission mode, and the arguments as YAML |
| Tool result | the tool's output, with the tool name in the subtitle; failures look the same, as text |
| Context banner | what the chat was given, neutral at the start and orange for an update after you changed skills |

| 卡片 | 內容 |
|---|---|
| User | 你的訊息，原文呈現 |
| Waiting | 回合執行中、尚未產出任何內容時顯示的無標題卡片 |
| Thinking | 模型的推理過程，以純文字串流呈現 |
| Response | 答案內容，生成時即以 Markdown 渲染，可含表格、連結與數學公式 |
| Tool Call | 工具名稱、權限模式，以及以 YAML 表示的參數 |
| Tool Result | 工具的輸出內容，工具名稱顯示於副標題；失敗結果同為文字，外觀與成功相同 |
| Context banner | 對話被賦予的內容；初始為中性色，變更技能後更新為橘色 |

Every card header shows an icon, a title, the card's token count, and a collapse arrow. While a turn is running, only the last twelve cards are expanded. Older cards stay collapsed to a header until you click them.

每張卡片的標題列顯示圖示、標題、該卡的 token 數量與摺疊箭頭。回合執行期間，只有最近 12 張卡片保持展開；更早的卡片收合為標題列，點擊後才會展開。

Hovering over a card header reveals two actions, both disabled while a generation is running. The trash icon deletes the turn that the card belongs to. The reload icon on a user card regenerates from that message and discards everything after it.

將滑鼠指標移到卡片標題上，會出現兩個按鈕；生成期間兩者皆無法使用。垃圾桶圖示會刪除該卡片所屬的整個回合；User 卡片上的重新載入圖示則會從該則訊息重新生成，並捨棄其後的所有內容。

### 1.4 Tab status and the input row — 分頁狀態與輸入列

The dot on each tab shows what the chat is doing, without opening it:

每個分頁上的圓點顯示該對話目前的狀態，不須開啟也能查看：

| Dot | Status | Meaning |
|---|---|---|
| grey | `EMPTY` | created, no messages yet |
| blue, blinking | `RUNNING` | generating |
| amber, blinking | `WAITING` | generating, paused for a tool approval |
| green | `FINISHED` | has messages, idle |
| red | `ERROR` | last turn failed or you stopped it |

| 圓點 | 狀態 | 含義 |
|---|---|---|
| 灰色 | 空白 | 已建立，尚無訊息 |
| 藍色（閃爍） | 執行中 | 正在生成 |
| 琥珀色（閃爍） | 等待核准 | 生成中，因等待工具核准而暫停 |
| 綠色 | 已完成 | 已有訊息，目前閒置 |
| 紅色 | 錯誤 | 上一回合失敗，或由你手動停止 |

`+` in the tab bar opens a new chat in the same panel. The new chat copies the skills, tool modes, and model of the chat you are on. `×` deletes the chat, and its file cannot be recovered.

分頁列上的「+」會在同一面板內開啟新對話，並沿用目前對話的技能、工具模式與模型設定。「×」會刪除該對話，其檔案無法復原。

The input row sits at the bottom of the panel. Type in the box, then press Enter or click Send. While a chat is generating, the Send button becomes Stop.

輸入列位於面板底部。在輸入框輸入文字後，按 Enter 或點選 Send 即可送出訊息。對話生成期間，Send 按鈕會變為 Stop。

Two controls appear when the pointer enters the row. A checkbox locks the Enter key, so you can write a multi-line message without sending it early. The auto-scroll toggle is on by default and fades out whenever it is paused.

滑鼠指標移入輸入列時，會顯示兩個控制項。勾選框用於鎖定 Enter 鍵，方便輸入多行文字而不致誤送出。自動捲動開關預設開啟，暫停時會淡出。

Stopping a turn keeps the partial transcript and marks the chat as stopped. The tab shows a red dot.

停止回合後，已產出的內容會保留，對話標記為已停止，對應分頁顯示紅色圓點。

### 1.5 Stopping, redoing, and the approval bar — 停止、重做與核准列

Stop cancels the current turn and keeps whatever it has produced so far.

Stop 會取消目前的回合，但保留已產出的內容。

The reload icon on a user card regenerates from that message and discards everything after it. The trash icon deletes the turn its card belongs to. Both let you redo a step without starting a new chat.

User 卡片上的重新載入圖示會從該則訊息重新生成，並捨棄其後的內容；垃圾桶圖示則刪除該卡片所屬的整個回合。兩者都能在不開啟新對話的情況下重做某一步驟。

The approval bar appears above the input row. When the model calls a tool set to Ask, generation pauses and the bar names the tool and the arguments it wants to pass.

核准列顯示在輸入列上方。當模型呼叫設為 Ask 模式的工具時，生成會暫停，核准列會列出工具名稱與其擬傳入的參數。

Approve runs the call and the turn continues. Deny skips the call and tells the model that execution was denied; usually you then get an answer built from what the model already had, or a second attempt by another route. Stop cancels the whole turn rather than deciding on that one call.

Approve 後，該次呼叫會執行，回合繼續。Deny 則跳過該次呼叫，並告知模型執行已被拒絕；此時模型通常會依既有資訊組織答案，或改走另一條路徑重試。Stop 則是取消整個回合，而非只對該次呼叫做決定。

Only Ask raises the bar. Allow runs the call straight through, and Block refuses it before the model sees anything.

只有 Ask 模式會觸發核准列。Allow 模式直接執行；Block 模式則在模型看到任何內容之前就拒絕。

Approvals belong to a single chat. A panel waiting for one blinks amber, so you can find it again after switching tabs.

核准只屬於單一對話。正在等待核准的面板會以琥珀色閃爍，方便你切換分頁後找回。

### 1.6 What the numbers at the bottom mean — 底部數字的意思

Five values sit above the input row and describe the active chat:

輸入列上方有五個數值，描述目前對話的狀態：

| Item | Meaning |
|---|---|
| Input tokens | the size of what the next turn will send: system prompt, loaded skills, and the whole conversation |
| Output tokens | what the chat has produced over all its turns |
| Activated | number of loaded skills |
| Allow / Ask / Block | tool counts in each permission mode |
| Model | the model name this chat uses |

| 項目 | 含義 |
|---|---|
| 輸入 token | 下一回合將送出的內容大小：系統提示詞、已載入的技能，以及整段對話 |
| 輸出 token | 該對話在所有回合累計產出的 token 數 |
| 已啟動 | 已載入的技能數量 |
| Allow／Ask／Block | 各權限模式下的工具數量 |
| 模型 | 該對話使用的模型名稱 |

The input token count climbs as the conversation grows, approaching the model's context window limit. Once it crosses the configured limit, Procoo asks the model to summarise the conversation and starts a new chat from that summary, so the work so far becomes the new chat's opening context.

輸入 token 數會隨對話增長而上升，逐漸逼近模型的上下文視窗上限。一旦超過設定的上限，Procoo 會請模型摘要對話，並以該摘要開啟新對話，把先前的工作濃縮為新對話的開場上下文。

The tool counts show what a turn will run into. A tool in Block is refused without asking, and a tool in Ask stops the turn at the approval bar.

工具數量顯示本回合可能遭遇的情況：設為 Block 的工具會直接遭到拒絕；設為 Ask 的工具則會讓回合停在核准列。

---

## 2. Skills — 技能

### 2.1 What a skill is and how it works — 技能是什麼、如何運作

A skill is a folder on disk under `capabilities/skills/`. Its entry point is a `SKILL.md` file, and it may also contain a `scripts/` folder.

技能是 `capabilities/skills/` 目錄下的一個資料夾。其入口為 `SKILL.md` 檔，資料夾內可另含一個 `scripts/` 子目錄。

The `SKILL.md` has two parts. A short metadata block at the top names the skill and describes what it does and when to use it. The body below holds the instructions: the steps of the job, the conventions to follow, and pointers to any reference files.

`SKILL.md` 分為兩部分。頂端是一小段中繼資料，為技能命名，並說明它做什麼、何時使用。下方的主體包含具體指令：工作步驟、須遵循的規範，以及指向參考檔案的指引。

When you tick a skill in the dock, two things happen on every turn from then on:

在技能側欄勾選一個技能後，自該刻起，每個回合都會發生兩件事：

1. The skill's full instructions are added to the system prompt that the model reads.
2. Each script in the skill's `scripts/` folder is registered as a tool the model may call. The model reads the script's docstring to learn what the tool does, what arguments it takes, and when to call it.

1. 技能的完整指令會加入系統提示詞，供模型每個回合讀取。
2. 技能 `scripts/` 目錄中的每個腳本，都會註冊為模型可呼叫的工具。模型透過 docstring 了解工具的功能、參數與適用時機。

The docstring description decides whether the tool gets used, used correctly, or not used at all. The model cannot infer what an argument means unless the description says so. A thin description therefore fails even when the code behind it is sound.

docstring 中的描述，決定工具是否會被使用、是否被正確使用，或根本不被使用。除非描述寫明，否則模型無法推斷參數的含義。因此，即使程式碼本身無誤，描述過簡仍會使工具失靈。

### 2.2 Navigating the skill panel — 操作技能側欄

Each panel has a narrow rail on its right edge. Click the rail to expand the skill dock over the transcript. While the dock is open, drag its left edge to resize it, or click anywhere outside it to close it.

每個面板的右緣有一條窄軌，點擊後會展開技能側欄，覆蓋在對話記錄之上。側欄展開時，可拖曳其左邊緣調整寬度，或點擊側欄以外的任意位置關閉。

**Searching.** The search field at the top of the dock filters the skill tree by name. Folders that match open; folders with no match are hidden. Click `×` to clear the search and restore the collapse state you had.

**搜尋。** 側欄頂端的搜尋欄可依名稱過濾技能樹。相符的資料夾會展開，沒有相符項目的資料夾則隱藏。點擊「×」可清除搜尋，並恢復先前的摺疊狀態。

**Ticking a skill.** Ticking a skill sends its instructions into the system prompt and registers its tools. Unticking removes the registration for the next turn. Instructions already in the conversation cannot be removed, because the agent keeps the old text in its history. Procoo therefore warns you when you untick a skill that has already run.

**勾選技能。** 勾選一個技能後，其指令會進入系統提示詞，其工具也會被註冊；取消勾選則自下一回合起停止註冊。已進入對話的指令無法移除，因為代理人會把舊文字保留在歷史中。因此，取消勾選一個已執行過的技能時，Procoo 會提出警告。

**Setting tool modes.** Tools sit under the skill that owns them. Each tool has a mode. Allow runs the call without asking; Ask raises the approval bar before it runs; Block refuses it before the model sees anything. Set each tool to the mode that matches how much you trust it.

**設定工具模式。** 工具列於其所屬技能之下，每個工具都有一種模式：Allow 會直接執行；Ask 會在執行前於核准列暫停；Block 會在模型看到任何內容之前就拒絕。請依你對工具的信任程度設定對應模式。

**Choosing the model.** The model dropdown in the dock lists every model in the config and marks the one this chat uses. Picking another changes the chat from its next turn, without reloading anything or losing the transcript.

**選擇模型。** 技能側欄中的模型下拉選單列出設定中的所有模型，並標記目前對話使用的模型。切換模型自下一回合生效，不會重新載入，也不會遺失對話記錄。

**Presets.** The preset field saves your current skill and tool selection under a name. Picking a saved preset later applies the whole selection at once.

**Preset。** Preset 欄位可將目前的技能與工具選擇以一個名稱儲存；日後選取該 Preset，即可一次套用整組設定。

All changes apply to the active chat immediately and are written into that chat's record.

所有變更會立即套用到目前的對話，並寫入該對話的記錄。

### 2.3 Two built-in skills — 兩個內建技能

Every Procoo chat loads two skills by default: `basic-ops` and `agent-principle`. Together they turn a raw language model into an agent that can do work for you.

每個 Procoo 對話預設載入兩個技能：`basic-ops` 與 `agent-principle`。這兩個技能共同把原始語言模型變成能實際執行工作的代理人。

**basic-ops: the hands**

**basic-ops：執行能力**

`basic-ops` gives the agent the tools to act on your machine. It registers a set of file tools for reading files and documents, creating and editing files, searching directories, running code or shell commands, and managing a records database.

`basic-ops` 賦予代理人操作本機檔案的能力。它註冊了一組檔案工具，可讀取檔案與文件、建立與編輯檔案、搜尋目錄、執行程式碼或 shell 指令，以及管理記錄資料庫。

Each tool has a clear job. `read_file` reads text files, PDFs, and images. `edit_file` creates, edits, or deletes a file. `search_dir` finds files by path pattern and by content. `execute_script` runs Python code or a shell command. `init_db` and `access_db` manage a records database.

每個工具各司其職。`read_file` 讀取文字檔、PDF 與圖片；`edit_file` 建立、編輯或刪除檔案；`search_dir` 依路徑模式與內容搜尋檔案；`execute_script` 執行 Python 程式碼或 shell 指令；`init_db` 與 `access_db` 管理記錄資料庫。

The skill also carries a tool selection policy: use the dedicated file tool for the job rather than a shell command. Read a file with `read_file`, not `cat`; edit with `edit_file`, not `sed`. The dedicated tools are safer, return structured results, and avoid shell injection risks.

該技能同時包含一條工具選擇準則：應使用專用工具，而非以 shell 指令替代。讀取檔案用 `read_file`，不用 `cat`；編輯檔案用 `edit_file`，不用 `sed`。專用工具更安全，能回傳結構化結果，並避免 shell 注入風險。

Without `basic-ops`, the model can talk but cannot touch anything on disk; it is only a chatbot. With it, the agent can read your code, edit your files, search your project, run your tests, and store records. That is the difference between a conversation and a worker.

少了 `basic-ops`，模型只能對話，無法觸及磁碟上的任何內容，仍只是個聊天機器人。有了它，代理人便能讀取程式碼、編輯檔案、搜尋專案、執行測試並儲存記錄。這正是「對話」與「實際執行」的差別。

**agent-principle: the method**

**agent-principle：工作方法**

`agent-principle` gives the agent a method for approaching work. It describes four phases:

`agent-principle` 賦予代理人一套工作方法，涵蓋四個階段：

| Phase | What it does |
|---|---|
| Align | Before the first step: read the skill and references, confirm the goal, deliverable, checking items, and assumptions. Wait for the user's go-ahead. |
| Proceed | Work to completion on the agreed method. Ask when something is ambiguous; decide when the material settles the question; record the decision. Keep momentum. |
| Check | Verify the work against the checking items agreed in Align. If it falls short, go back to Proceed. |
| Close and learn | Report the outcome and any deviations. Ask what missed the mark. Extract lessons from user corrections and write them into the skill or references after confirmation. |

| 階段 | 內容 |
|---|---|
| 對齊 | 動工前：閱讀技能說明與參考資料，確認目標、產出形式、檢查項目與假設。待使用者確認後再開始。 |
| 推進 | 依約定的方法執行至完成。遇有歧義時提問，材料足以判斷時做出決定並記錄，保持推進。 |
| 檢查 | 以對齊階段約定的檢查項目驗證成果；未達標則回到推進階段。 |
| 收束與學習 | 報告成果與偏離之處，詢問哪些方面未達標。從使用者的回饋中提煉教訓，經確認後寫入技能或參考資料。 |

The skill also sets the judgment rules. Ask when the purpose is ambiguous and a wrong guess is expensive; decide when the material settles the question; move on when the options are equally valid and the choice is reversible. It also sets the honesty standard: report where the work departed from the agreed method, state every assumption, and say early when something is wrong.

該技能也確立了判斷準則：目的模糊且誤判代價高時應提問；材料足以判斷時應做出決定並記錄；選項一樣好且可反悔時應繼續推進。它同時確立誠實標準：偏離約定方法時須報告，所有假設須明確陳述，出現問題時須及早說明。

Without `agent-principle`, the model starts doing whatever comes to mind and reports success regardless. With it, the model pauses to confirm intent, picks a method, executes with discipline, verifies its work, and reports honestly.

少了 `agent-principle`，模型會隨興而行，無論結果如何都回報已完成。有了它，模型會先確認意圖、選擇方法、有紀律地執行、驗證成果，並如實報告。

**Together: hands + method = an agent**

**執行能力＋工作方法＝代理人**

`basic-ops` is the capability layer, defining what the agent can do. `agent-principle` is the method layer, defining how the agent approaches work. The language model alone is a stateless text function: you ask, it answers, and nothing persists. Give it the tools and the method, and it becomes an agent. You hand it a task once, and it runs step after step on its own.

`basic-ops` 界定代理人「能做什麼」，`agent-principle` 界定代理人「該怎麼做」。語言模型本身是無狀態的純文字函數：有輸入才有輸出，輸出之後不留紀錄。賦予它工具與方法，它才成為代理人：只要交付一次任務，它便能自行逐步推進。

### 2.4 Three things you can put in a skill — 技能可以放的三種東西

A skill is useful because it moves knowledge you would otherwise retype into every conversation into a file the model reads once and applies every time. A skill can hold three kinds of content:

技能的價值在於：把原本每次對話都得重新輸入的內容，變成模型只需讀取一次、日後每次需要時即可套用的常駐知識。技能可容納的內容有三類：

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

A procedure is the set of steps you want the model to follow. Information is background knowledge you give the model: your naming conventions, your database schema, your company policy. A script is a program you write for the model to run. SKILL.md says when to call it and with what arguments, and the code does the actual work.

程序是你希望模型依循的步驟。資訊是你提供給模型的背景知識，例如命名規範、資料庫結構、公司政策。腳本是你撰寫好供模型執行的程式；SKILL.md 只說明呼叫時機與參數，實際工作由程式碼完成。

The point of all three is the same: a skill moves knowledge out of your keyboard and into files on disk, where the model reads it and applies it without you retyping it.

三者的共同點是：技能把知識從鍵盤移到磁碟上的檔案中，讓模型讀取後即可套用，不必再由你重複輸入。

### 2.5 Why skills make the agent better over time — 技能為什麼讓代理人越來越強

"Learning" with skills does not mean retraining the model. The weights do not change. When we say the agent learned from a skill, we mean a durable change was made to the skill files on disk, so the next similar task goes better.

在技能的語境中，「學習」不是重新訓練模型，模型的權重並未改變。當我們說代理人從技能中學到東西時，指的是磁碟上的技能檔案被實質地修改，讓下一次類似的任務執行得更順。

Improving a skill happens through three edit operations. **Append** adds new content, such as a step that came up, an edge case, or a worked example. **Refine** rewrites existing content, such as fixing a wrong step or sharpening a description. **Remove** deletes what is obsolete or harmful, such as dead scripts or outdated steps. A skill that only grows becomes bloated and contradictory, so all three operations are needed.

改進技能有三種編輯操作。**新增**用於補入新出現的步驟、邊界情況或範例；**修正**用於改寫錯誤的步驟，或把描述寫得更清楚；**移除**用於刪除過時或有害的內容，例如失效的腳本或過時的步驟。只增不刪會使技能臃腫且自相矛盾，因此三種操作缺一不可。

These edits follow a loop: act (run the task using the skill), observe (did it succeed, and where did it stumble), diagnose (missing knowledge means append, wrong knowledge means refine, stale knowledge means remove), apply (make the edit), and verify (re-run the task to confirm the change helps and breaks nothing else).

這些編輯構成一個循環：執行（用技能執行任務）、觀察（是否成功、在哪裡卡住）、診斷（知識不足則新增，知識有誤則修正，知識過時則移除）、套用（進行編輯）、驗證（重新執行任務，確認修改有效且未破壞其他部分）。

Over time, a maintained skill set compounds. Each task is slightly easier than the last, the skills sharpen, and the agent improves while the weights stay the same. An unmaintained skill set drifts: skills rot, records go stale, the agent confidently repeats outdated behavior, and trust erodes. Memory decays unless it is maintained.

長遠來看，持續維護的技能集會產生複利效果：每項任務都比前一次略為輕鬆，技能日益精確，代理人持續進步，而模型的權重絲毫未變。反之，缺乏維護的技能集會逐漸漂移：技能失靈、記錄過時、代理人自信地重複過時行為，信任也隨之磨損。記憶若不維護，便會衰退。

---

## 3. The mindset for building your skill set — 建立技能集的心法

### 3.1 Why and when to build a skill — 為什麼、何時建技能

The signal is simple: you find yourself pasting the same instructions or context into every conversation. When that happens, ask whether the model needs it every time or just this once.

什麼時候該建技能？訊號很直接：你發現自己每次對話都在貼上相同的指令或背景知識。一旦出現這種情況，就該自問：這些內容是模型每次都需要，還是只有這次需要？

If the answer is every time, it belongs in a skill. If it is just this once, a plain instruction in the chat is enough.

若答案是「每次都需要」，就該納入技能，成為模型可反覆讀取的常駐知識；若只是「這次需要」，在對話中直接說明即可，不必動用技能。

The purpose of a skill is to move knowledge out of your keyboard and into files on disk, where the model reads it and applies it on every relevant turn without you retyping it.

技能的本質，就是把知識從鍵盤移到磁碟上的檔案中，讓模型在每個相關回合都能讀取並套用，不必再由你重複輸入。

### 3.2 Direct processors — 直接處理器

A direct processor is a skill whose job is to produce an action or a reading. It either does something, or observes something and reports back.

直接處理器的職責很明確：產生一個動作，或提供一次讀值。換句話說，它要麼執行某項操作，要麼觀測某項狀態並回報結果。

Examples include a script that formats a file, a script that queries a database and returns a summary, and a procedure for cleaning a dataset. The boundary is clear: clear input, one job, clear output. You can test it in isolation without thinking about the rest of your skill set.

格式化檔案的腳本、查詢資料庫並回傳摘要的腳本，以及清理資料集的程序，都是直接處理器的典型範例。它們的共同特徵是邊界清晰：輸入明確、職責單一、輸出明確，因此可以獨立測試，無須顧慮技能集中的其他部分。

This is the obvious kind, and the first thing most people write. You notice a task you repeat, write down the steps or the script, and you have a direct processor.

這也是最好理解的類型，通常是多數人撰寫的第一個技能。當你注意到一項反覆進行的工作，只要寫下步驟或腳本，一個直接處理器便成形了。

### 3.3 Indirect processors — 間接處理器

An indirect processor is a skill whose job is to make other skills work better. It does not produce an action on its own. It holds the context, conventions, templates, and reference data that direct skills need to do their job correctly.

間接處理器的職責，與直接處理器不同：它本身不產出動作，而是讓其他技能運作得更好。它保存的是直接處理器正確執行工作所需的背景知識、規範、模板與參考資料。

The signal that you need one is that two direct skills reach for the same piece of context. Instead of copying that context into both, pull it out into a shared indirect skill. Both direct skills then point to it, and when the context changes you change it in one place.

什麼時候需要它？訊號很明確：當兩個直接處理器都需要同一塊背景知識時。與其把該背景複製到兩者之中，不如抽離出來，建立一個共用的間接技能。兩個直接處理器都指向它，日後背景變更時只需修改一處。

Indirect skills are the infrastructure of your skill set. They are the conventions, schemas, style guides, and reference documents that keep your direct skills from drifting apart.

整體來看，間接技能構成技能集的基礎設施。規範、資料結構、風格指南與參考文件，正是這些不直接執行工作的內容，使各直接處理器不至於各行其是、彼此偏離。

### 3.4 When skills grow — 技能長大時

As your skill set grows, two things happen: skills start to overlap, and skills start to drift.

技能集隨著使用而擴大，幾乎必然出現兩種現象：技能之間開始重疊，個別技能也開始漂移。

**Splitting.** When a skill does two different jobs, such as collecting data and formatting it, it is really two skills sharing one shell. The signal is that you find yourself writing "this part is for X and this part is for Y". That means the boundary is drawn in the wrong place. Split the skill: one direct processor for data collection, one for formatting, and, if both need the same context, a shared indirect skill for it.

**拆分。** 當一個技能同時承擔兩項不同的工作，例如既收集資料又格式化資料，它其實是兩個技能共用一個外殼。訊號是你開始寫「這部分給 X，那部分給 Y」，這表示邊界劃錯了地方，應予拆分：一個直接處理器負責收集，一個負責格式化；若兩者需要相同的背景知識，再抽離一個共用的間接技能。

**Drift.** A skill that has not been maintained starts to contradict itself: a step that is no longer true, a description that no longer matches what the skill does, or a script that was replaced but not removed. This is the decay mode. The three maintenance operations from section 2.5 (append, refine, remove) are how you fight it.

**漂移。** 長期未維護的技能會逐漸自相矛盾：某個步驟已不再成立，某個描述已與實際行為不符，或某個腳本已被替換卻未移除。這是技能衰敗的模式。第 2.5 節所述的三種維護操作（新增、修正、移除），正是對付漂移的手段。

**The coupling test.** One question tells you whether your boundaries are in the right place: can you change the inside of skill A without touching skill B? If not, the two are coupled where they should not be. The fix is usually to find the shared piece and pull it into an indirect skill.

**耦合測試。** 有一個問題可判斷邊界是否恰當：修改技能 A 的內部時，能否不觸及技能 B？若不能，兩者就在不該耦合的地方產生了耦合。解法通常是找出那個共用片段，把它抽離到間接技能中。

One principle ties it together: the job of skill design is to keep each skill's boundary clean, so the system of skills stays simple and maintainable as it grows.

貫穿以上各項的核心只有一句話：技能設計的關鍵，是維持每個技能的邊界清晰。只要邊界清晰，整個技能系統在持續成長中就能保持簡潔、易於維護。

---

## 4. The rest of Procoo — Procoo 的其他部分

### 4.1 Sessions — 工作階段

A session is a named group of chats, each with its own panel layout. Sessions live in the title bar. Click the session name to open the session list, where you can switch, create with `+`, or delete.

工作階段是由多個對話組成、可命名的群組，每個對話各有自己的面板配置。所有工作階段的管理入口都在標題列：點擊工作階段名稱即可開啟清單，從中切換、以「+」建立，或刪除既有工作階段。

Deleting a session also deletes its chats. `+ Win` creates a session and opens it in a window of its own.

刪除工作階段會同時刪除其下的所有對話。「+ Win」會建立一個新工作階段，並在獨立視窗中開啟。

Use sessions to separate your work contexts: one for coding, one for writing, one for research. Each keeps its own skills, tools, and panel arrangement.

工作階段可用來區隔不同的工作脈絡：一個用於寫程式，一個用於寫作，一個用於研究。每個工作階段各自保有獨立的技能、工具與面板配置。

### 4.2 Multi-window — 多視窗

`+ Win` in the session list creates a second window that runs a different session, with its own panels, tabs, and docks. Both windows read the same session list, so a session created in one appears in the other without a refresh.

清單中的「+ Win」會開啟第二個視窗，執行另一個工作階段；該視窗有自己的面板、分頁與技能側欄。兩個視窗共用同一份工作階段清單，因此任一個視窗建立的工作階段，都會立即出現在另一個視窗，不須重新整理。

Use it to run two sessions side by side: one doing the work, the other planning or monitoring.

常見的用法是並行執行兩個工作階段：一個負責實際工作，另一個負責規劃或監控。

### 4.3 Editor — 編輯器

The editor is a separate window with a file tree and a code pane. It opens from three places: Open Editor in the skill dock, Debug on an error notification, and Edit on an automation card. The last two also load the file they refer to.

編輯器是一個獨立視窗，包含檔案樹與程式碼區。開啟途徑有三：技能側欄中的 Open Editor、錯誤通知上的 Debug，以及自動化卡片上的 Edit。後兩者會同時載入它們所指向的檔案。

Files open read-only. Click Edit to unlock the buffer, make your changes, then click Save to write them to disk or Cancel to discard them.

檔案開啟時為唯讀。點選 Edit 可解鎖緩衝區，修改完成後按 Save 寫入磁碟，或按 Cancel 捨棄變更。

### 4.4 Automation — 自動化

An automation is a script that runs on a cron schedule or when an HTTP event arrives. It lives under `capabilities/automations/` as a directory containing an `AUTOMATION.py` file.

自動化是一個依 cron 排程或 HTTP 事件觸發而執行的腳本，存放於 `capabilities/automations/` 目錄下，以一個內含 `AUTOMATION.py` 的資料夾為單位。

The Automation page lists every automation Procoo finds, one card each. A card shows the name, description, activation type, schedule or event, and the result of the last run. The toggle enables or disables the automation. Run now starts it immediately, and the result arrives as a notification. Edit opens its `AUTOMATION.py` in the editor.

Automation 頁面列出 Procoo 找到的所有自動化項目，各以一張卡片呈現。每張卡片顯示名稱、描述、觸發類型、排程或事件，以及最近一次執行的結果。卡片上的開關用於啟用或停用該自動化；Run now 會立刻啟動，結果以通知形式呈現；Edit 則在編輯器中開啟其 `AUTOMATION.py`。

Notifications appear on the Notification tab with three badges: grey for logs, amber for info, and red for errors. An error card offers a Debug button that opens the failing automation in the editor.

通知顯示於 Notification 分頁，附有三種徽章：灰色代表 Log、琥珀色代表 Info、紅色代表 Error。錯誤卡片提供 Debug 按鈕，可在編輯器中開啟失敗的自動化項目。

### 4.5 Obsidian plugin — Obsidian 外掛

A local control server on port 12841 lets Obsidian open Procoo sessions. A marked span in a note stores a session ID. The context menu can open that session, or start one from the selected text.

本機控制伺服器（連接埠 12841）讓 Obsidian 能開啟 Procoo 工作階段。筆記中標記的文字片段會儲存一個工作階段 ID；透過右鍵選單，可以開啟該工作階段，或從選取的文字建立新的工作階段。

Use it to link your notes to your agent work: write a note, mark the relevant span, and open the session that has been working on it.

這個功能把筆記與代理人的工作串接起來：寫一篇筆記、標記相關片段，然後開啟一直在處理該內容的工作階段。

---

## 5. The config file — 設定檔

All settings live in `config/config.yaml`. To get started, copy the committed template `config/config_template.yaml`; the real file is gitignored.

所有設定都集中在 `config/config.yaml`。開始使用時，請複製版本庫中的範本 `config/config_template.yaml`；實際的設定檔已列入 `.gitignore`。

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
| `server` / `control_server` / `subagent` | 本機 HTTP 伺服器連接埠與 API 金鑰 |
| `basic_ops` | `read_file` 與 `access_db` 所呼叫的外部服務網址（OCR、語意搜尋） |

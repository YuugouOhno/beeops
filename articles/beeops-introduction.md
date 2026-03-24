---
title: "GitHub IssueをAIに渡したら勝手に実装してPRを送ってくる — せっかくなのでbeeopsをOSSとして公開してみた"
emoji: "🐝"
type: "tech"
topics: ["claudecode", "ai", "multiagent", "githubactions", "typescript"]
published: false
---

Claude Codeが出てから、個人開発の速度が変わった。でも「チームで使う」となると、少し困る点があった。既存のマルチエージェントシステムのほとんどが、ローカルのYAMLやMarkdownにタスクを積んでいく方式だからだ。

それをチームで共有しようとすると、「誰がこのYAMLを管理するの？」という問題が出てくる。

普通のエンジニアチームはGitHub Issuesでタスクを管理している。だったら、**GitHub IssuesをシングルソースオブトゥルースにしてAIが動けばいい**のでは？と思って作ったのが[beeops](https://github.com/GITHUB-ACCOUNT/beeops)です。

---

## 既存システムへの問題意識

AIエージェントシステムはここ1年で一気に増えた。将軍システム（将軍→家老→足軽）のような日本発のOSSも登場し、「AIにタスクを積んで自動実行」という体験は広まってきた。

ただ、これらの多くには共通の構造がある。

```
ローカルの指示ファイル（YAML/JSON）
  └─ タスク1: ...
  └─ タスク2: ...
  └─ タスク3: ...
```

個人で使う分にはこれで十分だ。でもチームで使うなら、「タスクはGitHub Issuesに積む」という普通の開発フローに合わせたい。

beeopsはその発想から作った。**`gh issue list`で取ってきたIssueをそのままAIのタスクキューにする。** GitHubのIssueにアサインするだけで、あとはAIが動く。

---

## 「並列 = 速い」は本質じゃない

マルチエージェントの記事を読むと「並列で走らせると速い！」という話がよく出てくる。確かにそうだが、実際にはレートリミットがあって、並列にしてもそこで詰まる。

スピードより大事なのは**コンテキストの分離**だと思っている。

たとえばIssueを1つ実装するとき、こういう問題が起きる：

> 「Issueの目標を達成できたかどうか判断する人」と「コードを書く人」が同じコンテキストにいると、実装の詳細に引きずられて判断が甘くなる。

実際のエンジニアチームでも、実装者とレビュアーを分けるのはそのためだ。「作った本人がレビューすると盲点が生まれる」という経験は誰でもある。

beeopsはこの分離を3層の構造で実現している。

---

## アーキテクチャ：Queen → Leader → Worker

```
👑 Queen (L1)
  GitHubのIssue一覧を取得し、優先度と依存関係を判断してLeaderを起動する
  コードは絶対に書かない。指揮するだけ。

  └─ 👑 Leader (L2) — Issue #42担当
       Issueの内容を読み、サブタスクに分解してWorkerを並列起動する
       Workerの成果を評価し、納得できるまで再実行させる
       最終的にPRを作成してQueenに報告する

         └─ ⚡ Worker-Coder (L3)   — サブタスク1実装
         └─ 🧪 Worker-Tester (L3)  — テスト作成

  └─ 🔮 Review Leader (L2) — PRをレビュー
       PRの変更量と複雑度を判定し、必要なReviewerを呼ぶ

         └─ 🔍 Worker-Code-Reviewer (L3)  — コード品質
         └─ 🛡 Worker-Security (L3)        — セキュリティ
         └─ 🧪 Worker-Test-Auditor (L3)    — テスト網羅性
```

**設計で大事にしたこと：**

- **Queenはコードを書かない**。queue.yamlの管理と起動指示だけ。コードを書こうとしたら即エラーになるよう指示書に書いてある
- **Leaderはgoal判定役**。「このIssueを達成できたか」を判断するのがLeaderの仕事で、実行はWorkerに任せる
- **Workerは実行専門**。与えられたサブタスクだけを見る。Issue全体の文脈は持たない
- **Review Leaderは独立**。実装に関わっていないので、フラットに評価できる

Reviewerが `fix_required` を返したら、Review LeaderがPRにコメントを書いてLeaderに差し戻す。Leaderはそのフィードバックをもとに再実装させる。これを最大3回繰り返す。

---

## 技術的な仕組み

### 環境変数でロールを切り替える

全エージェントは同じ `claude` CLI プロセスを使っている。起動時に環境変数を付与するだけで役割が変わる。

```bash
# Leader として起動
env BO_LEADER=1 claude --dangerously-skip-permissions ...

# Worker（Coder）として起動
env BO_WORKER_CODER=1 claude --dangerously-skip-permissions ...
```

`UserPromptSubmit` フック（`bo-prompt-context.py`）がこの環境変数を検出し、`agent-modes.json` のマッピングに従って対応するコンテキストファイルを注入する。

```json
// contexts/agent-modes.json（抜粋）
{
  "modes": {
    "BO_LEADER":       { "context": ["leader.md"] },
    "BO_WORKER_CODER": { "context": ["worker-base.md", "coder.md"] },
    "BO_WORKER_SECURITY": { "context": ["reviewer-base.md", "security-reviewer.md"] }
  }
}
```

「同じClaudeを環境変数1本で別エージェントとして動かす」のがこのシステムの肝だ。コンテキストファイルをローカルに展開して編集すれば、各エージェントの振る舞いを自由にカスタマイズできる。

### エージェント間通信はファイル + tmuxシグナル

リアルタイムのプロセス間通信は使っていない。シンプルに**ファイルとシグナル**で動く。

```
【下向き通信：親→子の指示】
.beeops/tasks/prompts/
  ├── leader-42.md       # Queen → Leader への指示書
  └── worker-42-1.md     # Leader → Worker への指示書

【上向き通信：子→親の完了通知】
.beeops/tasks/reports/
  ├── leader-42-summary.yaml        # 実装サマリー（PR URLなど）
  └── review-leader-42-verdict.yaml # approve / fix_required

【起床シグナル】
tmux wait-for -S queen-wake          # Leader→Queenに「終わったよ」
tmux wait-for -S leader-42-wake      # Worker→Leaderに「終わったよ」
```

Queenは `tmux wait-for queen-wake` でブロック待機しており、LeaderからシグナルがきたらYAMLレポートを読んで次のアクションを決める。**全ての状態がファイルに残るので、途中で死んでも再起動できる。**

### git worktreeでIssueごとに完全隔離

複数Issueを並列処理するとき、同じファイルを複数のLeaderが同時に編集する問題がある。beeopsはgit worktreeで解決している。

```bash
# Issue #42 と #43 が並列作業しても干渉しない
.beeops/worktrees/feat/issue-42/   # #42専用のリポジトリコピー
.beeops/worktrees/feat/issue-43/   # #43専用のリポジトリコピー
```

`node_modules` や `.next` はsymlinkで共有（ディスク節約）。PRマージ後にworktreeは自動削除される。

---

## 使い方

### インストール

```bash
npm install beeops
npx beeops init           # 個人利用（デフォルト）
npx beeops init --shared  # チーム共有（.claude/settings.json に登録）
npx beeops init -g        # グローバル（全プロジェクトで有効）
```

インストールすると以下が生成される：

- `.claude/commands/bee-dev.md` — `/bee-dev` コマンド
- `.claude/skills/bee-*/` — エージェント用スキル（10個）
- `.beeops/settings.json` — 実行設定（自動生成）

### 設定（`.beeops/settings.json`）

`npx beeops init` 時に自動生成される。GitHubのログイン名も自動検出して埋めてくれる。

```json
{
  "assignee": "GITHUB-ACCOUNT",  // "me" でも可。自分にアサインされたIssueだけ処理
  "github_username": "GITHUB-ACCOUNT",  // Issue質問時の@mention用
  "priority": "low",         // low以上のIssueを処理（high / medium / low）
  "skip_review": false,      // レビューフローをスキップするか
  "max_parallel_leaders": 2  // 並列で走るLeaderの数
}
```

`issues: [42, 55]` や `labels: ["bug"]` で処理対象を絞ることもできる。

`assignee: "me"` にしておけば、自分にアサインされたIssueだけをAIが処理する。チームの他の人のIssueには手をつけない。

### 起動

```
Claude Code で /bee-dev を実行
```

以下が自動で走る：

1. GitHubのIssue一覧を取得してqueue.yamlに同期
2. 優先度・依存関係を考慮してLeaderを起動
3. Leaderがタスク分解→Worker並列実行→PR作成
4. Review LeaderがPRをチェック
5. Approveされたら次のIssueへ

tmuxが起動してQueenと各Leaderのウィンドウが並ぶので、何が起きているかリアルタイムで見える。

---

## Agent Teamsとの違い

Claude Codeの公式機能「Agent Teams」とよく比較される。主な違いはここ。

| | Agent Teams | beeops |
|--|--|--|
| タスクの源泉 | 手動作成 | GitHub Issues自動同期 |
| タスク制御 | LLMが確率的に判断 | queue.yamlで明示的に管理 |
| ファイル競合 | 発生しうる | worktreeで完全分離 |
| セッション復帰 | 難しい（Teamateが消える） | queue.yaml/reportsで完全復帰 |
| レビューフロー | プロンプト指定・LLM判断 | 役割分離＋ループ制御＋YAML記録 |

Agent Teamsは「LLMに全部任せる」設計で、探索的なタスクに向いている。beeopsは「フローを決めて繰り返し動かす」設計で、GitHub Issueベースの開発ワークフローに向いている。

どちらが良い・悪いというより、**Claude Codeが1タスクをこなす精度はすでに十分高い。beeopsはその能力を「いつも同じフローで動かす」ための仕組み**だと思っている。

---

## カスタマイズ

```bash
npx beeops init --with-contexts
```

このオプションで各エージェントへの指示書（コンテキストファイル）がローカルに展開される。

```
.beeops/contexts/
  ├── ja/
  │   ├── queen.md          # Queenへの指示書
  │   ├── leader.md         # Leaderへの指示書
  │   ├── coder.md          # Coderへの指示書
  │   └── security-reviewer.md  # Security Reviewerへの指示書
  └── ...
```

これを編集するだけで、「セキュリティレビューはOWASP Top 10を必ずチェックする」「コーディング規約はこのプロジェクトのlintに従う」といったプロジェクト固有のルールを各エージェントに注入できる。

日本語・英語・中国語・スペイン語に対応しているので、ロケールに合わせたコンテキストを使える。

---

## まとめ

beeopsで実現したかったのは3つ：

1. **GitHub Issueがシングルソースオブトゥルース**
   チームメンバーが普通にIssueを積めばAIが処理する

2. **コンテキスト分離によるレビュー品質**
   実装と評価のコンテキストを分けることで、「自分で作って自分でOKを出す」を防ぐ

3. **フローの再現性**
   毎回同じフローが走る。ブラックボックスにならない

まだ発展途上ですが、実際に使ってみた感想や「こういう使い方してみた」「ここが不便」といったフィードバックをIssueでいただけると嬉しいです。

- GitHub: https://github.com/GITHUB-ACCOUNT/beeops
- npm: https://www.npmjs.com/package/beeops

```bash
npm install beeops && npx beeops init
```

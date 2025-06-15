## 🧾 前提の設定

本構成を動作させるには、以下のAWS側の事前設定が必要です。

### ✅ IAM設定

- Lambda 実行用 IAMロール（例：`lambda-cost-monitor-role`）に以下の権限が必要：
  - `ce:GetCostAndUsage`（Cost Explorer API呼び出し用）
  - `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`（CloudWatch Logs用）

### ✅ Lambda関数の作成

- ランタイム：Python 3.12（推奨）
- メモリ：128MB 以上
- タイムアウト：30秒程度で十分
- ハードコーディングされた環境変数（暫定）：
  - `USD_TO_JPY = 157.0`（必要に応じて環境変数化）

### ✅ Slack連携（※管理者作業）

- Slack App の作成 or Webhook URL の発行（通知先チャンネルの権限に応じて）
- Webhook URL は Lambda の環境変数で設定することを推奨

---

## 🛠 今回の構成・実行手順

本プロジェクトは以下の構成で動作します：

### 🧭 手順フロー

1. Lambda 関数 `aws-cost-to-slack` を AWS マネジメントコンソールから作成
2. コードをアップロード（`lambda_function.py`）
3. IAMロールに `ce:GetCostAndUsage` を付与
4. テスト実行し、CloudWatch Logs に出力されることを確認
5. Slack Webhook URL を取得（後日）
6. LambdaにWebhook URLを環境変数で登録し、Slack通知実装を追加
7. 最終的に EventBridge で週次スケジュール実行へ拡張

---

## ✨ 実装される主な機能

| 機能 | 説明 |
|------|------|
| ✅ 月初〜現在の AWS 利用料取得 | `ce:GetCostAndUsage` により USD 単位で取得 |
| ✅ サービスごとに分類 | `GroupBy: SERVICE` により明細化 |
| ✅ 金額の JPY 換算 | 任意の為替レート（例：157円/USD）で換算 |
| ✅ 金額の降順ソート | 最も高いコスト順に出力表示 |
| ✅ CloudWatch Logs への出力 | サービス名と金額をログ出力 |
| 🕒 Slack 通知機能（予定） | Webhook 経由でテキスト送信 |
| 🕒 EventBridge 連携（予定） | 定期実行の自動化 |

---


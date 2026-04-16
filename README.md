# AWS Cost Notifier

**AWS の利用料を毎日自動で集計・可視化して通知する Lambda** です。
Organizations 配下の全アカウントについて、月初から前日までのサービス別コストを集計し、指定した通知先に送ります。

## このプロジェクトについて

AWS の利用料は日々変動し、気付かないうちに予想外のコストが発生することも多い領域です。本プロジェクトは「**コストの日次可視化**」を目的に、**EventBridge Scheduler + Lambda + Cost Explorer API + 通知サービス**という組み合わせで軽量に実装しています。

個人の AWS 環境（Organizations でルート + 複数アカウントを管理、検証・学習用途）のコスト把握に使用していますが、同じパターンは以下のようなケースにも応用できます。

- 開発環境・本番環境を分けて運用しているチームでの日次コスト監視
- 部署別・プロジェクト別に AWS アカウントを分けている組織での予算管理
- 想定外コストの早期検知（特定サービスの急騰、消し忘れリソース等）

通知先は本リポジトリでは **LINE Messaging API** を使用していますが、Slack Webhook / Microsoft Teams Webhook / Amazon SNS / メール等、用途に応じて差し替え可能な構成です。

## 通知例

<img width="563" height="952" alt="image" src="https://github.com/user-attachments/assets/3b543849-8f54-4c69-aee5-9267062918f0" />


アカウントごとにサービス別コスト（上位 10 件）・小計が表示され、最後に全体合計を表示します。

## アーキテクチャ

```
EventBridge Scheduler (cron: 毎日 10:00 JST)
        │
        │ 日次 invoke
        ▼
AWS Lambda (Python)
        │
        ├──▶ Cost Explorer API (ce:GetCostAndUsage)
        │      └ LINKED_ACCOUNT × SERVICE で GroupBy
        │
        └──▶ LINE Messaging API (push)
              └ アカウント別・サービス別に整形したメッセージを送信
```

## 主な機能

- **期間集計** — 月初1日から前日までの累計コストを集計
- **アカウント別集計** — Organizations 配下の複数アカウントを `ACCOUNT_MAP` で名前付け
- **サービス別上位 10 件** — 各アカウント内で高コスト順にソート
- **通貨換算** — 環境変数 `USD_TO_JPY` のレートで円換算
- **月初の特別処理** — 毎月1日は前月1ヶ月分のフルレポートを送信

## セットアップ手順

### 1. IAM ロールを作成

Lambda 実行用の IAM ロールに以下の権限を付与します。

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ce:GetCostAndUsage"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "*"
        }
    ]
}
```

> Cost Explorer API は管理アカウント（Organizations の管理アカウント）から実行する必要があります。Linked Account からは呼び出せません。

### 2. Lambda 関数を作成

- **ランタイム**: Python 3.12 以上
- **メモリ**: 128 MB で十分
- **タイムアウト**: 30 秒（デフォルトの3秒では Cost Explorer 応答に間に合わないことがあるため**要変更**）

<img width="1756" height="411" alt="image" src="https://github.com/user-attachments/assets/fcb44b4f-065d-47cf-a3d3-abe3a989b1d0" />


### 3. コードをデプロイ

本リポジトリの `lambda_function.py` をコピペするか zip デプロイ。AWS Organizations 配下の実アカウント ID に合わせて `ACCOUNT_MAP` を編集してください。

```python
ACCOUNT_MAP = {
    "123456789012": "production",
    "234567890123": "staging",
    # ...
}
```

### 4. 環境変数を設定

Lambda の **設定** → **環境変数** で以下を登録します。

| 環境変数 | 用途 | 取得方法 |
|---|---|---|
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Messaging API のチャネルアクセストークン | LINE Developers Console |
| `LINE_USER_ID` | 通知先ユーザーの ID（`U...`） | LINE Bot を友だち追加後 Webhook で取得 |
| `USD_TO_JPY` | 円換算レート（例: `157`） | 任意に設定 |

<img width="1787" height="501" alt="image" src="https://github.com/user-attachments/assets/eced444e-9455-4118-849e-118fc22a2546" />


### 5. EventBridge Scheduler で日次実行を設定

AWS マネジメントコンソールで EventBridge → スケジューラ → スケジュールを作成します。

- **cron 式**: `0 10 * * ? *`（毎日 10:00 実行）
- **タイムゾーン**: `Asia/Tokyo`
- **ターゲット**: 作成した Lambda 関数を指定

<img width="1653" height="768" alt="image" src="https://github.com/user-attachments/assets/ad88dfe8-ea02-4cc7-b78b-afad3bdadc89" />


<img width="1830" height="328" alt="image" src="https://github.com/user-attachments/assets/8f55a46b-21e4-4f7c-ae87-f8bc5463e421" />


スケジューラ用の IAM ロール（`Amazon_EventBridge_Scheduler_LAMBDA`）に Lambda 起動権限が必要です。ウィザードから自動作成できます。

### 6. 動作確認

Lambda のテスト実行、または翌日 10:00 JST に自動実行されることを確認します。CloudWatch Logs に実行ログが残り、LINE に通知が届けば成功です。

## 他の通知先への切り替え

`send_line` 関数を差し替えるだけで他サービスへの通知に変更できます。

**Slack Webhook の場合：**

```python
def send_slack(message: str) -> None:
    webhook_url = os.environ['SLACK_WEBHOOK_URL']
    body = json.dumps({"text": message}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req)
```

環境変数 `SLACK_WEBHOOK_URL` を追加し、`send_line(message)` の呼び出しを `send_slack(message)` に変更するだけで切替完了です。

## ファイル構成

```
.
├── lambda_function.py    # Lambda エントリポイント
├── requirements.txt      # 依存ライブラリ（boto3 のみ、Lambda ランタイム同梱）
└── README.md             # 本ドキュメント
```

## 実装のポイント

- **依存ライブラリを最小化** — Lambda ランタイム同梱の `boto3` と標準ライブラリ（`urllib.request`, `json`, `datetime`）のみで構成。Layer 不要、zip も小さい
- **Cost Explorer API のリージョン** — `us-east-1` 固定。他リージョンから呼び出すとエラー
- **End パラメータは exclusive** — `TimePeriod.End` は指定日を含まない。月初当日は前月1日〜当月1日を指定することで前月フル期間を取得
- **アカウント別＋サービス別の GroupBy** — `LINKED_ACCOUNT` と `SERVICE` を組み合わせて階層的に集計

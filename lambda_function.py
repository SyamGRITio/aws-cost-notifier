"""
AWS Cost Notifier
-----------------
EventBridge Scheduler から日次実行され、月初〜前日までの AWS 利用料を
Organizations 配下のアカウント別・サービス別に集計して LINE に通知する Lambda。
"""

import boto3
import os
import json
import urllib.request
from datetime import datetime, timedelta, timezone
from collections import defaultdict

# AWS アカウント ID と表示名のマッピング
# Organizations 配下の各アカウントを列挙する（実際の AWS アカウント ID に置換して利用）
ACCOUNT_MAP = {
    "111111111111": "production",
    "222222222222": "staging",
    "333333333333": "identity",
    "444444444444": "management",
}


def lambda_handler(event, context):
    jst = timezone(timedelta(hours=9))
    today = datetime.now(jst).date()

    # 集計対象期間の決定
    # - 通常日: 月初から today まで（End は exclusive なので「前日までのコスト」を意味する）
    # - 月初当日: 前月1日 〜 当月1日（＝前月1ヶ月分）
    #
    # 以前のロジック (end = yesterday) では以下のバグがあった:
    #   - 毎月2日に Start==End となり ValidationException で落ちる
    #   - 毎月1日に End が前月末日になり、前月最終日のコストが欠損
    # これらを解消するため、End には today を渡す。
    if today.day == 1:
        current_month_first = today.replace(day=1)
        previous_month_first = (current_month_first - timedelta(days=1)).replace(day=1)
        start = previous_month_first.strftime('%Y-%m-%d')
        end = current_month_first.strftime('%Y-%m-%d')
    else:
        start = today.replace(day=1).strftime('%Y-%m-%d')
        end = today.strftime('%Y-%m-%d')

    # Cost Explorer API は us-east-1 固定
    ce = boto3.client('ce', region_name='us-east-1')
    result = ce.get_cost_and_usage(
        TimePeriod={'Start': start, 'End': end},
        Granularity='MONTHLY',
        Metrics=['UnblendedCost'],
        GroupBy=[
            {'Type': 'DIMENSION', 'Key': 'LINKED_ACCOUNT'},
            {'Type': 'DIMENSION', 'Key': 'SERVICE'},
        ],
    )

    usd_to_jpy = float(os.environ['USD_TO_JPY'])
    account_service_costs = defaultdict(list)
    account_totals = defaultdict(float)
    grand_total = 0.0

    groups = result['ResultsByTime'][0]['Groups']
    for g in groups:
        account_id, service = g['Keys']
        usd = float(g['Metrics']['UnblendedCost']['Amount'])
        if usd == 0:
            continue
        account_name = ACCOUNT_MAP.get(account_id, account_id)
        account_service_costs[account_name].append((service, usd))
        account_totals[account_name] += usd
        grand_total += usd

    # アカウント別にサービス上位 10 件を整形
    lines = []
    for account, services in account_service_costs.items():
        lines.append(f"\n【{account}】")
        services.sort(key=lambda x: x[1], reverse=True)
        for service, usd in services[:10]:
            jpy = round(usd * usd_to_jpy)
            lines.append(f"{service}: ¥{jpy:,}")
        total_jpy = round(account_totals[account] * usd_to_jpy)
        lines.append(f"小計: ¥{total_jpy:,}")

    grand_total_jpy = round(grand_total * usd_to_jpy)
    message = (
        f"📊 AWSコスト通知（アカウント別）\n"
        f"対象: {start} 〜 {end}\n"
        + "\n".join(lines)
        + f"\n\n【全体合計】\n¥{grand_total_jpy:,}"
    )

    send_line(message)
    return {"total_jpy": grand_total_jpy}


def send_line(message: str) -> None:
    """LINE Messaging API の push エンドポイントにメッセージを送信"""
    token = os.environ['LINE_CHANNEL_ACCESS_TOKEN']
    user_id = os.environ['LINE_USER_ID']
    body = json.dumps({
        "to": user_id,
        "messages": [{"type": "text", "text": message}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.line.me/v2/bot/message/push",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    urllib.request.urlopen(req)

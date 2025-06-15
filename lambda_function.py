import boto3
from datetime import datetime, timezone

def lambda_handler(event, context):
    now = datetime.now(timezone.utc)
    start = now.replace(day=1).strftime('%Y-%m-%d')
    end = now.strftime('%Y-%m-%d')

    ce = boto3.client('ce')
    result = ce.get_cost_and_usage(
        TimePeriod={'Start': start, 'End': end},
        Granularity='MONTHLY',
        Metrics=['UnblendedCost'],
        GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
    )

    usd_to_jpy = 157.0
    groups = result['ResultsByTime'][0]['Groups']

    service_costs = []
    for g in groups:
        service = g['Keys'][0]
        amount_usd = float(g['Metrics']['UnblendedCost']['Amount'])
        service_costs.append((service, amount_usd))

    # ✅ 正しく記述された並び替え
    service_costs.sort(key=lambda x: x[1], reverse=True)

    total_usd = 0.0
    for service, amount_usd in service_costs:
        amount_jpy = round(amount_usd * usd_to_jpy)
        total_usd += amount_usd
        print(f"{service}: 約 {amount_jpy:,} 円")

    total_jpy = round(total_usd * usd_to_jpy)
    print(f"合計: 約 {total_jpy:,} 円")

    return {"total_jpy": total_jpy}

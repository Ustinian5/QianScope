# ruff: noqa: E501
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import cast

from echo_swm.city.contracts import CityForecast
from echo_swm.city.population import CityWorld


def _delta_class(value: float, positive_is_good: bool = True) -> str:
    favorable = value >= 0 if positive_is_good else value <= 0
    return "positive" if favorable else "negative"


def write_city_report(world: CityWorld, forecast: CityForecast, path: Path) -> None:
    control = next(iter(forecast.branch_trajectories))
    metric_labels = {
        "life_satisfaction": "生活满意度",
        "government_trust": "政府信任",
        "economic_confidence": "经济信心",
        "consumption_index": "消费指数",
        "employment_rate": "就业概率",
        "congestion_index": "拥堵指数",
        "health_system_load": "医疗负载",
        "rumor_belief": "传言相信度",
        "stress": "压力",
        "commute_minutes": "平均通勤分钟",
        "organization_vitality": "企业组织活力",
        "public_service_reliability": "公共服务可靠性",
        "policy_cost_100m_cny": "累计政策成本（亿元）",
    }
    bad_when_positive = {
        "congestion_index",
        "health_system_load",
        "rumor_belief",
        "stress",
        "commute_minutes",
        "policy_cost_100m_cny",
    }
    delta_rows: list[str] = []
    for branch, values in forecast.counterfactual_deltas.items():
        for metric, value in values.items():
            delta_rows.append(
                f"<tr><td>{html.escape(branch)}</td><td>{metric_labels.get(metric, metric)}</td>"
                f"<td class='{_delta_class(value, metric not in bad_when_positive)}'>{value:+.4f}</td></tr>"
            )
    district_rows: list[str] = []
    for item in forecast.final_district_metrics:
        if item["branch_id"] == control:
            continue
        metrics = cast(dict[str, dict[str, float]], item["metrics"])
        district_rows.append(
            "<tr>"
            f"<td>{html.escape(str(item['branch_id']))}</td>"
            f"<td>{html.escape(str(item['district_name']))}</td>"
            f"<td>{metrics['life_satisfaction']['p50']:.3f}</td>"
            f"<td>{metrics['economic_confidence']['p50']:.3f}</td>"
            f"<td>{metrics['employment_probability']['p50']:.3f}</td>"
            f"<td>{metrics['congestion_index']['p50']:.3f}</td>"
            f"<td>{metrics['health_system_load']['p50']:.3f}</td>"
            f"<td>{metrics['rumor_belief']['p50']:.3f}</td>"
            "</tr>"
        )
    anchor_rows = "".join(
        "<tr>"
        f"<td>{district.anchor.name_zh}</td>"
        f"<td>{district.population_2025 / 10_000:.2f} 万</td>"
        f"<td>{district.gdp_2025_100m:.1f} 亿元</td>"
        f"<td>{district.anchor.urbanization_2024:.1%}</td>"
        "</tr>"
        for district in world.anchors.districts
    )
    trajectory_json = json.dumps(
        {
            branch: [
                {
                    "day": point.day,
                    **{metric: band.p50 for metric, band in point.metrics.items()},
                }
                for point in points
            ]
            for branch, points in forecast.branch_trajectories.items()
        },
        ensure_ascii=False,
    )
    page = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>模拟苏州 · 黔镜 QianScope</title>
<style>
:root{{--ink:#14212b;--muted:#63727d;--line:#dce5e9;--paper:#f5f8f7;--blue:#176b87;--green:#147d64;--red:#b84444}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 system-ui,"Microsoft YaHei",sans-serif}}
main{{max-width:1280px;margin:auto;padding:28px}}header{{background:#102d38;color:white;padding:28px;border-radius:16px}}
h1{{margin:0 0 8px;font-size:30px}}h2{{margin-top:32px}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:18px}}
.card{{background:white;border:1px solid var(--line);border-radius:12px;padding:16px}}.value{{font-size:24px;font-weight:700;color:var(--blue)}}
table{{width:100%;border-collapse:collapse;background:white}}th,td{{text-align:left;padding:9px;border-bottom:1px solid var(--line)}}th{{background:#e9f1f3;position:sticky;top:0}}
.scroll{{overflow:auto;max-height:470px;border:1px solid var(--line);border-radius:12px}}.positive{{color:var(--green);font-weight:700}}.negative{{color:var(--red);font-weight:700}}
.note{{color:var(--muted);background:#edf2f1;padding:14px;border-left:4px solid var(--blue)}}canvas{{width:100%;height:320px;background:white;border:1px solid var(--line);border-radius:12px}}
@media(max-width:800px){{.grid{{grid-template-columns:1fr 1fr}}main{{padding:14px}}}}
</style></head><body><main>
<header><h1>模拟苏州 · 城市社会世界模型</h1><p>主体 × 家庭 × 机构 × 空间 × 出行 × 经济 × 公共服务 × 信息传播</p>
<div class="grid"><div><b>{forecast.prototype_count:,}</b><br>合成原型人</div><div><b>{forecast.represented_population / 10_000:.2f} 万</b><br>代表人口</div><div><b>{world.graph.edge_count:,}</b><br>多层关系边</div><div><b>{len(forecast.branch_trajectories)}</b><br>反事实分支</div></div></header>
<section class="grid"><div class="card"><div class="value">1304.77 万</div>2025 常住人口</div><div class="card"><div class="value">82.9%</div>城镇化率</div><div class="card"><div class="value">2.76951 万亿</div>地区生产总值</div><div class="card"><div class="value">{forecast.query.samples}</div>K 路径/分支</div></section>
<h2>30 日中位轨迹</h2><canvas id="chart" width="1200" height="320"></canvas>
<h2>相对 {html.escape(control)} 的期末变化</h2><div class="scroll"><table><thead><tr><th>分支</th><th>指标</th><th>Δ</th></tr></thead><tbody>{"".join(delta_rows)}</tbody></table></div>
<h2>区县期末状态（p50）</h2><div class="scroll"><table><thead><tr><th>分支</th><th>区县</th><th>满意度</th><th>经济信心</th><th>就业</th><th>拥堵</th><th>医疗负载</th><th>传言</th></tr></thead><tbody>{"".join(district_rows)}</tbody></table></div>
<h2>公开统计约束</h2><div class="scroll"><table><thead><tr><th>区县</th><th>缩放后人口</th><th>缩放后 GDP</th><th>2024 城镇化</th></tr></thead><tbody>{anchor_rows}</tbody></table></div>
<h2>边界</h2><p class="note">市级与区县级约束来自苏州市统计局公开统计。个人、家庭、关系、机构行为和事件效应均为合成原型与显式机制假设，不是对真实居民的复制，也不是已验证的政策因果效果。{html.escape(forecast.disclaimer)}</p>
</main><script>
const data={trajectory_json};const canvas=document.getElementById('chart');const c=canvas.getContext('2d');
const colors=['#176b87','#d9862b','#147d64','#8b5fbf'];const metric='life_satisfaction';
c.font='13px system-ui';c.fillStyle='#fff';c.fillRect(0,0,1200,320);c.strokeStyle='#dce5e9';
for(let i=0;i<6;i++){{let y=30+i*48;c.beginPath();c.moveTo(55,y);c.lineTo(1170,y);c.stroke();}}
Object.entries(data).forEach(([name,rows],idx)=>{{c.strokeStyle=colors[idx%colors.length];c.lineWidth=3;c.beginPath();
rows.forEach((r,i)=>{{let x=60+i*(1100/(rows.length-1));let y=285-(r[metric]-0.35)*520;if(i===0)c.moveTo(x,y);else c.lineTo(x,y)}});c.stroke();c.fillStyle=colors[idx%colors.length];c.fillText(name,75+idx*220,20)}});
c.fillStyle='#63727d';c.fillText('生活满意度 p50',1050,305);
</script></body></html>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")

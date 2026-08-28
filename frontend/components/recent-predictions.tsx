'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

type RecentItem = {
  run_id: string;
  title: string;
  created_at: string;
  conclusion: string;
  agent_count: number;
};

export function RecentPredictions({ limit = 20 }: { limit?: number }) {
  const [items, setItems] = useState<RecentItem[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    fetch(`/api/qianscope/v1/predictions?limit=${limit}`, { cache: 'no-store' })
      .then(async (response) => {
        if (!response.ok) throw new Error('offline');
        return await response.json() as { items?: RecentItem[] };
      })
      .then((body) => setItems(body.items || []))
      .catch(() => setItems([]))
      .finally(() => setLoaded(true));
  }, [limit]);

  if (!loaded) return <div className="empty-projects">正在读取最近项目…</div>;
  if (!items.length) {
    return (
      <div className="empty-projects">
        <strong>还没有预测项目</strong>
        <p>从一个你真正关心的问题开始，通用 10 题模板已经准备好了。</p>
        <Link href="/predict">新建第一个预测</Link>
      </div>
    );
  }
  return (
    <div className="recent-grid">
      {items.map((item) => (
        <Link className="recent-card" href={`/predict?run=${item.run_id}`} key={item.run_id}>
          <span>{new Date(item.created_at).toLocaleDateString('zh-CN')}</span>
          <h3>{item.title}</h3>
          <p>{item.conclusion}</p>
          <small>{item.agent_count.toLocaleString('zh-CN')} 个虚拟参与者</small>
        </Link>
      ))}
    </div>
  );
}
